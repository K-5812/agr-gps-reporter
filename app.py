
import io, os, re, tempfile
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle

st.set_page_config(page_title="AGR GPS Reporter", page_icon="🏉", layout="centered")
BASE=os.path.dirname(os.path.abspath(__file__))
LOGO=os.path.join(BASE,"logo_agr.jpg")

OBJECTIVES={
"PRIMERA LINEA":{"DISTANCIA":4500,"HML":600,"ACC":25,"RHIE":18,"VEL.MAX":30},
"SEGUNDA LINEA":{"DISTANCIA":5000,"HML":650,"ACC":30,"RHIE":20,"VEL.MAX":32},
"TERCERA LINEA":{"DISTANCIA":5500,"HML":700,"ACC":40,"RHIE":20,"VEL.MAX":32},
"BACK":{"DISTANCIA":6000,"HML":800,"ACC":45,"RHIE":22,"VEL.MAX":34}}
GW={"DISTANCIA":.20,"HML":.25,"ACC":.20,"RHIE":.20,"VEL.MAX":.15}
IW={"DISTANCIA":.10,"HML":.35,"ACC":.30,"RHIE":.25}

def norm(s): return re.sub(r"\s+"," ",str(s).strip().upper())
def find_col(cols,cands):
    for c in cols:
        nc=norm(c)
        if any(norm(x)==nc or norm(x) in nc for x in cands): return c
def pos(v):
    s=norm(v)
    if "PRIMER" in s or s=="1L": return "PRIMERA LINEA"
    if "SEGUND" in s or s=="2L": return "SEGUNDA LINEA"
    if "TERCER" in s or s=="3L": return "TERCERA LINEA"
    if "BACK" in s or "TRES CUART" in s: return "BACK"
    return s
def vel(v):
    try:
        x=float(v); return x/1000 if x>100 else x
    except: return np.nan

def load_excel(file):
    df=pd.read_excel(file)
    mp={
      "Name":find_col(df.columns,["NAME","NOMBRE","JUGADOR"]),
      "PUESTO":find_col(df.columns,["PUESTO","POSICION"]),
      "MIN":find_col(df.columns,["TIEMPO TOTAL","MINUTOS","MIN"]),
      "DISTANCIA":find_col(df.columns,["TOTAL DISTANCE","DISTANCIA TOTAL","DISTANCE"]),
      "HML":find_col(df.columns,["HML DISTANCE","HML"]),
      "ACC":find_col(df.columns,["ACCELERATIONS","ACELERACIONES","ACC"]),
      "RHIE":find_col(df.columns,["RHIE"]),
      "VEL.MAX":find_col(df.columns,["VELOC. MAX","VELOCIDAD MAX","VEL.MAX","MAX SPEED"])}
    miss=[k for k,v in mp.items() if v is None]
    if miss: raise ValueError("No pude reconocer: "+", ".join(miss))
    out=pd.DataFrame({
      "Name":df[mp["Name"]].astype(str),"PUESTO":df[mp["PUESTO"]].map(pos),
      "MIN":pd.to_numeric(df[mp["MIN"]],errors="coerce"),
      "DISTANCIA":pd.to_numeric(df[mp["DISTANCIA"]],errors="coerce"),
      "HML":pd.to_numeric(df[mp["HML"]],errors="coerce"),
      "ACC":pd.to_numeric(df[mp["ACC"]],errors="coerce"),
      "RHIE":pd.to_numeric(df[mp["RHIE"]],errors="coerce"),
      "VEL.MAX":df[mp["VEL.MAX"]].map(vel)}).dropna(subset=["MIN"])
    bad=out[~out.PUESTO.isin(OBJECTIVES)]
    if len(bad): raise ValueError("Puesto no reconocido: "+", ".join(sorted(set(bad.PUESTO))))
    return out

def target(p,m,half=False):
    b=OBJECTIVES[p["PUESTO"]][m]
    if m=="VEL.MAX": return b
    return b*min(float(p["MIN"]),40 if half else 80)/80

def calc(df,half=False):
    arr=[]
    for _,r in df.iterrows():
        p=r.to_dict()
        pc={m:p[m]/target(p,m,half)*100 if target(p,m,half) else 0 for m in GW}
        p["GLOBAL"]=min(sum(min(pc[m],120)*GW[m] for m in GW)/1.2,100)
        rp={}
        for m in IW:
            rp[m]=(p[m]/p["MIN"])/(OBJECTIVES[p["PUESTO"]][m]/80)*100 if p["MIN"] else 0
        p["INT"]=min(sum(min(rp[m],150)*IW[m] for m in IW),100)
        p["PCTS"]=pc; p["RATEP"]=rp; arr.append(p)
    return arr

def sem(v): return "#C62828" if v<70 else ("#F9A825" if v<90 else "#2E7D32")

def report(df,title,half=False):
    data=calc(df,half); tg=np.mean([p["GLOBAL"] for p in data]); ti=np.mean([p["INT"] for p in data])
    temp=tempfile.mkdtemp(); meta={"DISTANCIA":("DISTANCIA TOTAL","m"),"HML":("HML DISTANCE","m"),"ACC":("ACELERACIONES","n"),"RHIE":("RHIE","n"),"VEL.MAX":("VELOCIDAD MAXIMA","km/h")}
    charts=[]
    for m,(ttl,unit) in meta.items():
        vals=[p[m] for p in data]; goals=[target(p,m,half) for p in data]; pcs=[p["PCTS"][m] for p in data]
        x=np.arange(len(data)); fig,ax=plt.subplots(figsize=(7.4,8.7))
        bars=ax.bar(x,vals,width=.62,color=[sem(v) for v in pcs]); ax.plot(x,goals,lw=2.3,marker="o",ms=4.5,color="#B71C1C",label="Objetivo")
        ymax=max(vals+goals+[1])*1.28; ax.set_ylim(0,ymax); ax.set_title(ttl,fontsize=18,fontweight="bold")
        ax.set_ylabel(unit); ax.set_xticks(x); ax.set_xticklabels([p["Name"] for p in data],rotation=48,ha="right",fontsize=9)
        ax.grid(axis="y",alpha=.16); ax.legend(frameon=False); ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        for b,v,pc in zip(bars,vals,pcs):
            ax.text(b.get_x()+b.get_width()/2,max(v*.48,ymax*.045),f"{v:g}",ha="center",va="center",color="white",fontsize=9,fontweight="bold")
            ax.text(b.get_x()+b.get_width()/2,v+ymax*.018,f"{pc:.0f}%",ha="center",fontsize=9,fontweight="bold")
        fig.tight_layout(); cp=os.path.join(temp,m.replace(".","")+".png"); fig.savefig(cp,dpi=160,bbox_inches="tight"); plt.close(fig); charts.append((m,cp))
    rank=sorted(data,key=lambda p:p["INT"],reverse=True)
    fig,ax=plt.subplots(figsize=(7.4,6.2)); rr=rank[::-1]; y=np.arange(len(rr))
    bars=ax.barh(y,[p["INT"] for p in rr],color=[sem(p["INT"]) for p in rr]); ax.set_yticks(y); ax.set_yticklabels([p["Name"] for p in rr])
    ax.set_xlim(0,105); ax.set_title("INTENSIDAD POR MINUTO",fontsize=17,fontweight="bold"); ax.axvline(ti,ls="--",lw=2,color="#333333",label=f"Promedio {ti:.1f}")
    ax.grid(axis="x",alpha=.15); ax.legend(frameon=False)
    for b,p in zip(bars,rr): ax.text(min(p["INT"]-2,98),b.get_y()+b.get_height()/2,f"{p['INT']:.1f}",ha="right",va="center",color="white",fontweight="bold")
    fig.tight_layout(); ic=os.path.join(temp,"int.png"); fig.savefig(ic,dpi=170,bbox_inches="tight"); plt.close(fig)
    pdf=os.path.join(temp,"AGR_Reporte.pdf")
    stl=getSampleStyleSheet()
    stl.add(ParagraphStyle(name="Cov",parent=stl["Title"],fontSize=24,alignment=1))
    stl.add(ParagraphStyle(name="Sub",parent=stl["Heading2"],fontSize=15,alignment=1,textColor=colors.HexColor("#C62828")))
    stl.add(ParagraphStyle(name="Sec",parent=stl["Heading2"],fontSize=15,spaceAfter=8))
    stl.add(ParagraphStyle(name="BodyX",parent=stl["BodyText"],fontSize=9.3,leading=13,spaceAfter=6))
    doc=SimpleDocTemplate(pdf,pagesize=A4,leftMargin=1.2*cm,rightMargin=1.2*cm,topMargin=1*cm,bottomMargin=1*cm)
    story=[Spacer(1,.3*cm)]
    if os.path.exists(LOGO): story += [Image(LOGO,width=4.2*cm,height=4.2*cm)]
    story += [Paragraph("ALTA GRACIA RUGBY",stl["Cov"]),Paragraph("REPORTE GPS - "+title,stl["Sub"]),PageBreak()]
    if os.path.exists(LOGO): story += [Image(LOGO,width=1.4*cm,height=1.4*cm)]
    story += [Paragraph("RESUMEN EJECUTIVO",stl["Sec"]),Paragraph(f"<b>Rendimiento Global AGR:</b> {tg:.1f}/100 &nbsp; | &nbsp; <b>Intensidad/minuto:</b> {ti:.1f}/100",stl["BodyX"])]
    rows=[["#","JUGADOR","MIN","GLOBAL","INT./MIN"]]+[[str(i),p["Name"],f"{p['MIN']:.0f}",f"{p['GLOBAL']:.1f}",f"{p['INT']:.1f}"] for i,p in enumerate(rank,1)]
    tb=Table(rows,colWidths=[.8*cm,5.5*cm,1.5*cm,2.2*cm,2.3*cm],repeatRows=1)
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#202020")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#D0D0D0")),("FONTSIZE",(0,0),(-1,-1),8.5),("ALIGN",(2,1),(-1,-1),"CENTER")]))
    story += [tb,PageBreak()]
    for m,cp in charts:
        story += [Paragraph(meta[m][0],stl["Sec"]),Image(cp,width=16.9*cm,height=19.7*cm),PageBreak()]
    story += [Paragraph("INFORME FINAL - INTENSIDAD RELATIVA",stl["Sec"]),Paragraph("HML/min 35% + Aceleraciones/min 30% + RHIE/min 25% + Distancia/min 10%. Velocidad maxima se mantiene como valor pico dentro del Rendimiento Global.",stl["BodyX"]),Image(ic,width=16.3*cm,height=13.6*cm)]
    detail=[["JUGADOR","MIN","m/min","HML/min","ACC/min","RHIE/min","INT."]]
    for p in rank: detail.append([p["Name"],f"{p['MIN']:.0f}",f"{p['DISTANCIA']/p['MIN']:.1f}",f"{p['HML']/p['MIN']:.1f}",f"{p['ACC']/p['MIN']:.2f}",f"{p['RHIE']/p['MIN']:.2f}",f"{p['INT']:.1f}"])
    dt=Table(detail,colWidths=[3.7*cm,1.1*cm,1.7*cm,1.8*cm,1.8*cm,1.8*cm,1.4*cm])
    dt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#202020")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#D0D0D0")),("FONTSIZE",(0,0),(-1,-1),7.5),("ALIGN",(1,1),(-1,-1),"CENTER")]))
    story += [dt,Spacer(1,.3*cm)]
    for p in rank:
        if p["MIN"]<=20 and p["RATEP"]["ACC"]>=90:
            story.append(Paragraph(f"<b>{p['Name']}:</b> por los {p['MIN']:.0f} minutos jugados, mostro una <b>buena intensidad en aceleraciones</b>: {p['ACC']:.0f} acciones ({p['ACC']/p['MIN']:.2f}/min).",stl["BodyX"]))
    doc.build(story)
    return open(pdf,"rb").read(),data

if os.path.exists(LOGO): st.image(LOGO,width=120)
st.title("AGR GPS REPORTER")
st.caption("Alta Gracia Rugby · GPS · Rendimiento e intensidad relativa")
mode=st.radio("Tipo de reporte",["Partido completo","1T + 2T"],horizontal=True)

if mode=="Partido completo":
    f=st.file_uploader("Cargar Excel GPS",type=["xlsx","xls"])
    if f and st.button("GENERAR REPORTE PDF",type="primary",use_container_width=True):
        try:
            df=load_excel(f); pdf,data=report(df,"PARTIDO COMPLETO",False)
            st.success("Reporte generado correctamente")
            st.download_button("DESCARGAR PDF",pdf,"AGR_Reporte_GPS.pdf","application/pdf",use_container_width=True)
            st.subheader("Vista rápida")
            st.dataframe(pd.DataFrame([{"Jugador":p["Name"],"Min":p["MIN"],"Global":round(p["GLOBAL"],1),"Intensidad/min":round(p["INT"],1)} for p in sorted(data,key=lambda x:x["INT"],reverse=True)]),hide_index=True,use_container_width=True)
        except Exception as e: st.error(str(e))
else:
    f1=st.file_uploader("Cargar Excel 1T",type=["xlsx","xls"],key="1")
    f2=st.file_uploader("Cargar Excel 2T",type=["xlsx","xls"],key="2")
    if f1 and f2 and st.button("GENERAR REPORTES",type="primary",use_container_width=True):
        try:
            d1=load_excel(f1); d2=load_excel(f2)
            p1,_=report(d1,"PRIMER TIEMPO",True); p2,_=report(d2,"SEGUNDO TIEMPO",True)
            both=pd.concat([d1,d2],ignore_index=True).groupby(["Name","PUESTO"],as_index=False).agg({"MIN":"sum","DISTANCIA":"sum","HML":"sum","ACC":"sum","RHIE":"sum","VEL.MAX":"max"})
            pc,_=report(both,"COMPARATIVO 1T + 2T",False)
            st.success("Reportes generados")
            st.download_button("DESCARGAR 1T",p1,"AGR_1T.pdf","application/pdf",use_container_width=True)
            st.download_button("DESCARGAR 2T",p2,"AGR_2T.pdf","application/pdf",use_container_width=True)
            st.download_button("DESCARGAR COMPARATIVO",pc,"AGR_Comparativo.pdf","application/pdf",use_container_width=True)
        except Exception as e: st.error(str(e))

st.divider()
st.caption("Volumen relativo a minutos jugados · DLS excluido · Velocidad máxima = valor pico")
