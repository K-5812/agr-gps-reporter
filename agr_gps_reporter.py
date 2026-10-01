import os, re, math, tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle

APP_DIR=os.path.dirname(os.path.abspath(__file__))
LOGO=os.path.join(APP_DIR,"logo_agr.jpg")

OBJECTIVES={
"PRIMERA LINEA":{"DISTANCIA":4500,"HML":600,"ACC":25,"RHIE":18,"VEL.MAX":30},
"SEGUNDA LINEA":{"DISTANCIA":5000,"HML":650,"ACC":30,"RHIE":20,"VEL.MAX":32},
"TERCERA LINEA":{"DISTANCIA":5500,"HML":700,"ACC":40,"RHIE":20,"VEL.MAX":32},
"BACK":{"DISTANCIA":6000,"HML":800,"ACC":45,"RHIE":22,"VEL.MAX":34},
}
GLOBAL_W={"DISTANCIA":.20,"HML":.25,"ACC":.20,"RHIE":.20,"VEL.MAX":.15}
INT_W={"DISTANCIA":.10,"HML":.35,"ACC":.30,"RHIE":.25}

def norm(s):
    s=str(s).strip().upper()
    s=re.sub(r"\s+"," ",s)
    return s

def find_col(cols, candidates):
    ncols={norm(c):c for c in cols}
    for cand in candidates:
        for nc,orig in ncols.items():
            if norm(cand)==nc or norm(cand) in nc:
                return orig
    return None

def position(v):
    s=norm(v)
    if "PRIMER" in s or s in ("1L","PRIMERA"): return "PRIMERA LINEA"
    if "SEGUND" in s or s in ("2L","SEGUNDA"): return "SEGUNDA LINEA"
    if "TERCER" in s or s in ("3L","TERCERA"): return "TERCERA LINEA"
    if "BACK" in s or "TRES CUART" in s: return "BACK"
    return s

def speed(v):
    try:
        x=float(v)
        return x/1000 if x>100 else x
    except: return np.nan

def load_excel(path):
    df=pd.read_excel(path)
    c_name=find_col(df.columns,["NAME","NOMBRE","JUGADOR"])
    c_pos=find_col(df.columns,["PUESTO","POSICION"])
    c_min=find_col(df.columns,["TIEMPO TOTAL","MINUTOS","MIN"])
    c_dist=find_col(df.columns,["TOTAL DISTANCE","DISTANCIA TOTAL","DISTANCE"])
    c_hml=find_col(df.columns,["HML DISTANCE","HML"])
    c_acc=find_col(df.columns,["ACCELERATIONS","ACELERACIONES","ACC"])
    c_rhie=find_col(df.columns,["RHIE"])
    c_vel=find_col(df.columns,["VELOC. MAX","VELOCIDAD MAX","VEL.MAX","MAX SPEED"])
    missing=[n for n,c in [("Nombre",c_name),("Puesto",c_pos),("Minutos",c_min),("Distancia",c_dist),("HML",c_hml),("Aceleraciones",c_acc),("RHIE",c_rhie),("Velocidad Max",c_vel)] if c is None]
    if missing: raise ValueError("Faltan columnas: "+", ".join(missing))
    out=pd.DataFrame({
        "Name":df[c_name].astype(str),
        "PUESTO":df[c_pos].map(position),
        "MIN":pd.to_numeric(df[c_min],errors="coerce"),
        "DISTANCIA":pd.to_numeric(df[c_dist],errors="coerce"),
        "HML":pd.to_numeric(df[c_hml],errors="coerce"),
        "ACC":pd.to_numeric(df[c_acc],errors="coerce"),
        "RHIE":pd.to_numeric(df[c_rhie],errors="coerce"),
        "VEL.MAX":df[c_vel].map(speed),
    }).dropna(subset=["MIN"])
    bad=out[~out["PUESTO"].isin(OBJECTIVES)]
    if len(bad): raise ValueError("Puestos no reconocidos: "+", ".join(sorted(set(bad["PUESTO"]))))
    return out

def target(row,m,half=False):
    base=OBJECTIVES[row["PUESTO"]][m]
    if m=="VEL.MAX": return base
    cap=40 if half else 80
    return base*min(float(row["MIN"]),cap)/80

def metrics(df,half=False):
    rows=[]
    for _,r in df.iterrows():
        p=r.to_dict()
        pcts={}
        for m in ["DISTANCIA","HML","ACC","RHIE","VEL.MAX"]:
            t=target(p,m,half)
            pcts[m]=float(p[m])/t*100 if t else 0
        raw=sum(min(pcts[m],120)*GLOBAL_W[m] for m in GLOBAL_W)
        global_score=min(raw/1.2,100)
        ratep={}
        for m in INT_W:
            ar=float(p[m])/float(p["MIN"]) if p["MIN"] else 0
            tr=OBJECTIVES[p["PUESTO"]][m]/80
            ratep[m]=ar/tr*100 if tr else 0
        intensity=min(sum(min(ratep[m],150)*INT_W[m] for m in INT_W),100)
        p.update({"PCTS":pcts,"GLOBAL":global_score,"INT":intensity,"RATEP":ratep})
        rows.append(p)
    return rows

def sem(v):
    return "#C62828" if v<70 else ("#F9A825" if v<90 else "#2E7D32")

def add_logo(story,w=1.4):
    if os.path.exists(LOGO): story.append(Image(LOGO,width=w*cm,height=w*cm))

def make_report(df,out_pdf,title="PARTIDO COMPLETO",half=False):
    data=metrics(df,half)
    team_global=np.mean([p["GLOBAL"] for p in data])
    team_int=np.mean([p["INT"] for p in data])
    work=os.path.join(os.path.dirname(out_pdf),"_agr_charts")
    os.makedirs(work,exist_ok=True)
    meta={"DISTANCIA":("DISTANCIA TOTAL","m"),"HML":("HML DISTANCE","m"),"ACC":("ACELERACIONES","n"),"RHIE":("RHIE","n"),"VEL.MAX":("VELOCIDAD MAXIMA","km/h")}
    charts=[]
    for m,(ttl,unit) in meta.items():
        vals=[p[m] for p in data]; tg=[target(p,m,half) for p in data]; pcs=[p["PCTS"][m] for p in data]
        x=np.arange(len(data)); fig,ax=plt.subplots(figsize=(7.4,8.7))
        bars=ax.bar(x,vals,width=.62,color=[sem(v) for v in pcs])
        ax.plot(x,tg,lw=2.3,marker="o",ms=4.5,color="#B71C1C",label="Objetivo")
        ymax=max(vals+tg+[1])*1.28; ax.set_ylim(0,ymax)
        ax.set_title(ttl,fontsize=18,fontweight="bold",pad=16); ax.set_ylabel(unit)
        ax.set_xticks(x); ax.set_xticklabels([p["Name"] for p in data],rotation=48,ha="right",fontsize=9)
        ax.grid(axis="y",alpha=.16); ax.legend(frameon=False,loc="upper left")
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        for b,v,pc in zip(bars,vals,pcs):
            ax.text(b.get_x()+b.get_width()/2,max(v*.48,ymax*.045),f"{v:g}",ha="center",va="center",color="white",fontsize=9,fontweight="bold")
            ax.text(b.get_x()+b.get_width()/2,v+ymax*.018,f"{pc:.0f}%",ha="center",fontsize=9,fontweight="bold")
        fig.tight_layout()
        cp=os.path.join(work,m.replace(".","")+".png"); fig.savefig(cp,dpi=170,bbox_inches="tight"); plt.close(fig); charts.append((m,cp))
    rank=sorted(data,key=lambda p:p["INT"],reverse=True)
    fig,ax=plt.subplots(figsize=(7.4,6.3)); rr=rank[::-1]; y=np.arange(len(rr))
    bars=ax.barh(y,[p["INT"] for p in rr],color=[sem(p["INT"]) for p in rr])
    ax.set_yticks(y); ax.set_yticklabels([p["Name"] for p in rr],fontsize=10); ax.set_xlim(0,105)
    ax.set_xlabel("Indice de intensidad / 100"); ax.set_title("INTENSIDAD POR MINUTO",fontsize=17,fontweight="bold",pad=14)
    ax.axvline(team_int,ls="--",lw=2,color="#333333",label=f"Promedio equipo {team_int:.1f}")
    ax.grid(axis="x",alpha=.15); ax.legend(frameon=False,loc="lower right")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    for b,p in zip(bars,rr):
        ax.text(min(p["INT"]-2,98),b.get_y()+b.get_height()/2,f"{p['INT']:.1f}",ha="right",va="center",color="white",fontweight="bold")
    fig.tight_layout(); intchart=os.path.join(work,"intensidad.png"); fig.savefig(intchart,dpi=180,bbox_inches="tight"); plt.close(fig)

    st=getSampleStyleSheet()
    st.add(ParagraphStyle(name="Cov",parent=st["Title"],fontSize=24,leading=28,alignment=1))
    st.add(ParagraphStyle(name="Sub",parent=st["Heading2"],fontSize=15,alignment=1,textColor=colors.HexColor("#C62828")))
    st.add(ParagraphStyle(name="Sec",parent=st["Heading2"],fontSize=15,spaceAfter=8))
    st.add(ParagraphStyle(name="BodyX",parent=st["BodyText"],fontSize=9.4,leading=13,spaceAfter=6))
    st.add(ParagraphStyle(name="SmallX",parent=st["BodyText"],fontSize=8.5,leading=11,alignment=1,textColor=colors.HexColor("#555555")))
    doc=SimpleDocTemplate(out_pdf,pagesize=A4,leftMargin=1.2*cm,rightMargin=1.2*cm,topMargin=1*cm,bottomMargin=1*cm)
    story=[Spacer(1,.3*cm)]
    if os.path.exists(LOGO): story += [Image(LOGO,width=4.3*cm,height=4.3*cm),Spacer(1,.2*cm)]
    story += [Paragraph("ALTA GRACIA RUGBY",st["Cov"]),Paragraph("REPORTE GPS - "+title,st["Sub"]),Spacer(1,.6*cm),
              Paragraph("DISTANCIA | HML | ACELERACIONES | RHIE | VELOCIDAD MAXIMA",st["SmallX"]),PageBreak()]
    add_logo(story); story += [Paragraph("RESUMEN EJECUTIVO",st["Sec"]),
        Paragraph(f"<b>Rendimiento Global AGR del equipo:</b> {team_global:.1f}/100 &nbsp;&nbsp; | &nbsp;&nbsp; <b>Intensidad/minuto:</b> {team_int:.1f}/100.",st["BodyX"])]
    rows=[["#","JUGADOR","PUESTO","MIN","GLOBAL","INT./MIN"]]
    for i,p in enumerate(rank,1): rows.append([str(i),p["Name"],p["PUESTO"],f"{p['MIN']:.0f}",f"{p['GLOBAL']:.1f}",f"{p['INT']:.1f}"])
    t=Table(rows,colWidths=[.6*cm,4.3*cm,3.3*cm,1.2*cm,1.6*cm,1.8*cm],repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#202020")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7.8),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#D0D0D0")),
        ("ALIGN",(0,0),(0,-1),"CENTER"),("ALIGN",(3,1),(-1,-1),"CENTER"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F7F7F7")])]))
    story += [t,PageBreak()]
    for m,cp in charts:
        add_logo(story,1.2); story += [Paragraph(meta[m][0],st["Sec"]),Paragraph("Valor real dentro de la barra | % del objetivo arriba | linea roja = objetivo ajustado",st["SmallX"]),Image(cp,width=16.9*cm,height=19.7*cm),PageBreak()]
    add_logo(story); story += [Paragraph("INFORME FINAL - INTENSIDAD RELATIVA",st["Sec"]),
        Paragraph("La Intensidad/minuto relativiza la produccion al tiempo efectivo en cancha: HML/min 35%, Aceleraciones/min 30%, RHIE/min 25% y Distancia/min 10%. La Velocidad Maxima permanece dentro del Rendimiento Global por ser un valor pico.",st["BodyX"]),
        Image(intchart,width=16.4*cm,height=13.8*cm)]
    detail=[["JUGADOR","MIN","m/min","HML/min","ACC/min","RHIE/min","INT."]]
    for p in rank:
        detail.append([p["Name"],f"{p['MIN']:.0f}",f"{p['DISTANCIA']/p['MIN']:.1f}",f"{p['HML']/p['MIN']:.1f}",f"{p['ACC']/p['MIN']:.2f}",f"{p['RHIE']/p['MIN']:.2f}",f"{p['INT']:.1f}"])
    dt=Table(detail,colWidths=[3.7*cm,1.1*cm,1.7*cm,1.8*cm,1.8*cm,1.8*cm,1.4*cm],repeatRows=1)
    dt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#202020")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7.5),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#D0D0D0")),
        ("ALIGN",(1,1),(-1,-1),"CENTER"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F7F7F7")])]))
    story += [dt,Spacer(1,.35*cm)]
    # Automatic short interpretation of short-minute players with strong acceleration rate.
    for p in rank:
        if p["MIN"] <= 20 and p["RATEP"]["ACC"] >= 90:
            story.append(Paragraph(f"<b>{p['Name']}:</b> por los {p['MIN']:.0f} minutos jugados, mostro una <b>buena intensidad en aceleraciones</b>: {p['ACC']:.0f} acciones, equivalentes a {p['ACC']/p['MIN']:.2f} aceleraciones/min.",st["BodyX"]))
    doc.build(story)

def choose_full():
    path=filedialog.askopenfilename(filetypes=[("Excel","*.xlsx *.xls")])
    if not path:return
    try:
        df=load_excel(path)
        out=filedialog.asksaveasfilename(defaultextension=".pdf",initialfile="AGR_Reporte_GPS.pdf",filetypes=[("PDF","*.pdf")])
        if not out:return
        make_report(df,out,"PARTIDO COMPLETO",False)
        messagebox.showinfo("AGR GPS","Reporte generado correctamente:\n"+out)
    except Exception as e: messagebox.showerror("Error",str(e))

def choose_halves():
    p1=filedialog.askopenfilename(title="Seleccionar Excel 1T",filetypes=[("Excel","*.xlsx *.xls")])
    if not p1:return
    p2=filedialog.askopenfilename(title="Seleccionar Excel 2T",filetypes=[("Excel","*.xlsx *.xls")])
    if not p2:return
    folder=filedialog.askdirectory(title="Carpeta para guardar los reportes")
    if not folder:return
    try:
        d1=load_excel(p1); d2=load_excel(p2)
        make_report(d1,os.path.join(folder,"AGR_1T.pdf"),"PRIMER TIEMPO",True)
        make_report(d2,os.path.join(folder,"AGR_2T.pdf"),"SEGUNDO TIEMPO",True)
        # Comparativo simple: combina ambos tiempos por jugador para una lectura global.
        both=pd.concat([d1.assign(TIEMPO="1T"),d2.assign(TIEMPO="2T")],ignore_index=True)
        agg=both.groupby(["Name","PUESTO"],as_index=False).agg({"MIN":"sum","DISTANCIA":"sum","HML":"sum","ACC":"sum","RHIE":"sum","VEL.MAX":"max"})
        make_report(agg,os.path.join(folder,"AGR_COMPARATIVO_1T_2T.pdf"),"COMPARATIVO 1T + 2T",False)
        messagebox.showinfo("AGR GPS","Generados 3 reportes en:\n"+folder)
    except Exception as e: messagebox.showerror("Error",str(e))

root=tk.Tk(); root.title("AGR GPS Reporter"); root.geometry("560x390"); root.resizable(False,False)
tk.Label(root,text="ALTA GRACIA RUGBY",font=("Arial",22,"bold")).pack(pady=(35,4))
tk.Label(root,text="GPS REPORTER",font=("Arial",15,"bold"),fg="#C62828").pack()
tk.Label(root,text="Objetivos por puesto + ajuste por minutos + intensidad relativa",font=("Arial",10)).pack(pady=(5,25))
tk.Button(root,text="CARGAR EXCEL - PARTIDO COMPLETO",font=("Arial",12,"bold"),width=38,height=2,command=choose_full).pack(pady=8)
tk.Button(root,text="CARGAR 1T + 2T",font=("Arial",12,"bold"),width=38,height=2,command=choose_halves).pack(pady=8)
tk.Label(root,text="Volumen ajustado a minutos | m/min | HML/min | ACC/min | RHIE/min\nVelocidad maxima = valor pico sin ajuste temporal",font=("Arial",9),justify="center").pack(pady=22)
root.mainloop()
