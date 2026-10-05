import os
import sys
import subprocess
import io
import sqlite3
from datetime import datetime

# --- AUTO-ARRANQUE INTELIGENTE ---
if "STREAMLIT_RUNNING" not in os.environ:
    os.environ["STREAMLIT_RUNNING"] = "true"
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", sys.argv[0]])
    except Exception as e:
        print(f"Error al iniciar automáticamente: {e}")
    sys.exit()

import streamlit as st
import pandas as pd
import requests
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Configuración de la página
st.set_page_config(page_title="Sistema de Almacén y Compras", layout="wide")

# --- ESTILOS CSS PERSONALIZADOS PARA BOTONES Y ESTATUS COMPACTOS ---
st.markdown("""
    <style>
    /* Estilo unificado y compacto para botones y distintivo de estatus horizontal */
    div.stButton > button, div.stDownloadButton > button, .estatus-badge-horizontal {
        padding: 4px 4px !important;
        font-size: 10px !important;
        min-height: 28px !important;
        max-height: 28px !important;
        width: 100% !important;
        border-radius: 4px !important;
        font-weight: bold !important;
        text-align: center !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-sizing: border-box !important;
        margin: 0 !important;
    }
    
    .estatus-badge-horizontal {
        border: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONFIGURACIÓN DE TELEGRAM ---
TELEGRAM_TOKEN = "8973356521:AAFK_y6mzmHWIli2PmyuC4RcrplJpufLtwQ"
TELEGRAM_CHAT_ID = "-1004497817391"
TELEGRAM_TOPIC_ESTATUS = 20  # ID correcto del tema Estatus en Telegram

def enviar_alerta_telegram(mensaje, message_thread_id=None):
    """Envía un mensaje a Telegram permitiendo opcionalmente especificar el tema (thread_id)"""
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": mensaje
            }
            if message_thread_id:
                payload["message_thread_id"] = message_thread_id
            
            response = requests.post(url, json=payload, timeout=15)
            if not response.ok:
                print(f"❌ Error de Telegram: {response.text}")
            else:
                print("✅ Mensaje enviado a Telegram correctamente.")
        except Exception as e:
            print(f"❌ Excepción al enviar notificación a Telegram: {e}")

# --- CONFIGURACIÓN DE BASE DE DATOS SQLITE (.db) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "sistema_almacen.db")

def inicializar_db():
    """Crea las tablas necesarias en la base de datos SQLite si no existen"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS catalogos (
            proveedor TEXT,
            producto TEXT,
            minimo TEXT,
            maximo TEXT,
            unidad TEXT,
            pedido TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            fecha TEXT,
            proveedor TEXT,
            productos_detalle TEXT,
            estatus TEXT
        )
    ''')
    conn.commit()
    conn.close()

def cargar_datos_locales():
    """Carga los proveedores, catálogos y pedidos desde la base de datos SQLite"""
    inicializar_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Cargar catálogos
    cursor.execute("SELECT proveedor, producto, minimo, maximo, unidad, pedido FROM catalogos")
    rows = cursor.fetchall()
    cat_dict = {}
    for prov, prod, min_v, max_v, un_v, ped_v in rows:
        if prov not in cat_dict:
            cat_dict[prov] = []
        cat_dict[prov].append({
            "PRODUCTO": prod,
            "MINIMO": min_v,
            "MAXIMO": max_v,
            "UNIDAD": un_v,
            "PEDIDO": ped_v
        })
    
    st.session_state.proveedores_catalogo = {}
    for prov, items in cat_dict.items():
        st.session_state.proveedores_catalogo[prov] = pd.DataFrame(items)
        
    # Cargar pedidos
    cursor.execute("SELECT id, fecha, proveedor, productos_detalle, estatus FROM orders")
    order_rows = cursor.fetchall()
    if order_rows:
        orders_data = []
        for r in order_rows:
            orders_data.append({
                "ID": r[0],
                "Fecha": r[1],
                "PROVEEDOR": r[2],
                "PRODUCTOS_DETALLE": r[3],
                "Estatus": r[4]
            })
        st.session_state.orders = pd.DataFrame(orders_data)
    else:
        st.session_state.orders = pd.DataFrame(columns=[
            "ID", "Fecha", "PROVEEDOR", "PRODUCTOS_DETALLE", "Estatus"
        ])
    conn.close()

def guardar_datos_locales():
    """Guarda los proveedores, catálogos y pedidos en la base de datos SQLite"""
    inicializar_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Reemplazar catálogos
    cursor.execute("DELETE FROM catalogos")
    for prov, df in st.session_state.proveedores_catalogo.items():
        for _, row in df.iterrows():
            cursor.execute(
                "INSERT INTO catalogos (proveedor, producto, minimo, maximo, unidad, pedido) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    prov,
                    str(row.get("PRODUCTO", "")),
                    str(row.get("MINIMO", "")),
                    str(row.get("MAXIMO", "")),
                    str(row.get("UNIDAD", "")),
                    str(row.get("PEDIDO", ""))
                )
            )
            
    # Reemplazar pedidos
    cursor.execute("DELETE FROM orders")
    for _, row in st.session_state.orders.iterrows():
        cursor.execute(
            "INSERT INTO orders (id, fecha, proveedor, productos_detalle, estatus) VALUES (?, ?, ?, ?, ?)",
            (
                int(row["ID"]),
                str(row["Fecha"]),
                str(row["PROVEEDOR"]),
                str(row["PRODUCTOS_DETALLE"]),
                str(row["Estatus"])
            )
        )
        
    conn.commit()
    conn.close()

# Base de datos simulada de usuarios en la sesión
if "users" not in st.session_state:
    st.session_state.users = {
        "admin": {"password": "123", "role": "Administrador"},
        "almacen1": {"password": "123", "role": "Usuario"}
    }

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

if "proveedores_catalogo" not in st.session_state:
    st.session_state.proveedores_catalogo = {}
    st.session_state.orders = pd.DataFrame(columns=[
        "ID", "Fecha", "PROVEEDOR", "PRODUCTOS_DETALLE", "Estatus"
    ])
    cargar_datos_locales()

if "prov_crear_pedido_key" not in st.session_state:
    st.session_state.prov_crear_pedido_key = "-- Selecciona un proveedor --"

if "reset_pedido_form" not in st.session_state:
    st.session_state.reset_pedido_form = False

if st.session_state.reset_pedido_form:
    st.session_state.prov_crear_pedido_key = "-- Selecciona un proveedor --"
    st.session_state.reset_pedido_form = False

def login_screen():
    st.title("🔐 Inicio de Sesión - Sistema de Almacén y Compras")
    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")
        
        if submit:
            if username in st.session_state.users and st.session_state.users[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = st.session_state.users[username]["role"]
                st.success("¡Bienvenido!")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

def generar_pdf(pedido_id, proveedor, productos_info, estatus, fecha):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "REPORTE DE PEDIDO - ALMACÉN A COMPRAS")
    p.setFont("Helvetica", 10)
    p.drawString(50, height - 70, f"Fecha de emisión: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    p.line(50, height - 80, width - 50, height - 80)
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 110, f"Pedido ID: #{pedido_id}")
    p.drawString(50, height - 130, f"PROVEEDOR: {proveedor}")
    p.drawString(50, height - 150, f"Estatus Actual: {estatus}")
    p.drawString(50, height - 170, f"Fecha de Registro: {fecha}")
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 210, "Detalle de Productos:")
    
    p.setFont("Helvetica", 10)
    text_y = height - 230
    for linea in str(productos_info).split("\n"):
        if not linea.strip():
            continue
        
        # Limpieza para dejar solo nombre de producto y cantidad
        partes = linea.split("|")
        prod_val = ""
        cant_val = ""
        
        for p_text in partes:
            p_text = p_text.strip()
            if p_text.startswith("PRODUCTO:"):
                prod_val = p_text.replace("PRODUCTO:", "").strip()
            elif p_text.startswith("PEDIDO:"):
                cant_val = p_text.replace("PEDIDO:", "").strip()
                
        if prod_val and cant_val:
            linea_final = f"{prod_val}: {cant_val}"
        else:
            linea_final = linea.replace("PRODUCTO:", "").replace("PEDIDO:", "").replace("MÍNIMO:", "").replace("MÁXIMO:", "").replace("UNIDAD:", "").strip()
        
        p.drawString(70, text_y, f"• {linea_final}")
        text_y -= 20
        if text_y < 50:
            p.showPage()
            text_y = height - 50
            
    p.save()
    buffer.seek(0)
    return buffer

if not st.session_state.logged_in:
    login_screen()
else:
    st.sidebar.title(f"👤 Hola, {st.session_state.username}")
    st.sidebar.text(f"Rol: {st.session_state.role}")
    
    menu = ["📦 Gestión, Catálogos e Historial"]
    if st.session_state.role == "Administrador":
        menu.append("👥 Administración de Usuarios")
    
    choice = st.sidebar.selectbox("Menú de Navegación", menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

    if choice == "📦 Gestión, Catálogos e Historial":
        st.title("📦 Control de Almacén, Compras y Catálogos")
        
        st.markdown("""
        **Estatus del Sistema:**
        * 🔴 **Pedido realizado** | 🟡 **Se mandó a proveedor** | 🟢 **Entregado**
        """)
        
        tab1, tab2, tab3 = st.tabs([
            "📝 Crear Pedido", 
            "📂 Catálogo de Proveedores", 
            "📊 Historial General"
        ])
        
        with tab1:
            st.subheader("Crear Nuevo Pedido basado en Catálogo")
            
            proveedores_disponibles = list(st.session_state.proveedores_catalogo.keys())
            opciones_proveedor = ["-- Selecciona un proveedor --"] + proveedores_disponibles
            
            if st.session_state.prov_crear_pedido_key not in opciones_proveedor:
                st.session_state.prov_crear_pedido_key = "-- Selecciona un proveedor --"
            
            proveedor_seleccionado = st.selectbox(
                "Selecciona el Proveedor", 
                opciones_proveedor,
                key="prov_crear_pedido_key"
            )
            
            df_a_pedir = pd.DataFrame(columns=["PRODUCTO", "MINIMO", "MAXIMO", "UNIDAD", "PEDIDO"])
            
            if proveedor_seleccionado != "-- Selecciona un proveedor --":
                df_a_pedir = st.session_state.proveedores_catalogo[proveedor_seleccionado].copy()
                for col in ["MINIMO", "MAXIMO", "UNIDAD", "PEDIDO"]:
                    if col in df_a_pedir.columns:
                        df_a_pedir[col] = df_a_pedir[col].astype(str).replace("nan", "")
                if "PEDIDO" not in df_a_pedir.columns:
                    df_a_pedir["PEDIDO"] = ""
            
            st.markdown("##### Ajusta las cantidades en la columna **PEDIDO**:")
            df_editado = st.data_editor(df_a_pedir, num_rows="dynamic", use_container_width=True, key="editor_pedido_nuevo")
            
            if st.button("💾 Guardar y Emitir Pedido"):
                if proveedor_seleccionado != "-- Selecciona un proveedor --":
                    new_id = int(len(st.session_state.orders) + 1)
                    current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    resumen_prods = ""
                    resumen_telegram_prods = ""
                    for _, r in df_editado.iterrows():
                        prod = str(r.get("PRODUCTO", "")).strip()
                        pedido_cant = str(r.get("PEDIDO", "")).strip()
                        if prod and prod != "nan" and pedido_cant and pedido_cant != "" and pedido_cant != "nan" and pedido_cant != "None":
                            resumen_prods += f"PRODUCTO: {prod} | PEDIDO: {pedido_cant}\n"
                            resumen_telegram_prods += f"• {prod}: {pedido_cant}\n"
                    
                    if resumen_prods:
                        new_row = pd.DataFrame([{
                            "ID": new_id,
                            "Fecha": current_date,
                            "PROVEEDOR": proveedor_seleccionado,
                            "PRODUCTOS_DETALLE": resumen_prods.strip(),
                            "Estatus": "Pedido realizado"
                        }])
                        st.session_state.orders = pd.concat([st.session_state.orders, new_row], ignore_index=True)
                        
                        guardar_datos_locales()
                        
                        mensaje_telegram = (
                            f"📦 NUEVO PEDIDO\n\n"
                            f"Proveedor: {proveedor_seleccionado}\n"
                            f"Fecha: {current_date}\n"
                            f"Número de Pedido: #{new_id}\n\n"
                            f"Productos:\n{resumen_telegram_prods}"
                        )
                        enviar_alerta_telegram(mensaje_telegram)
                        
                        st.session_state.reset_pedido_form = True
                        if "editor_pedido_nuevo" in st.session_state:
                            del st.session_state["editor_pedido_nuevo"]
                        
                        st.toast(f"🚀 ¡Pedido #{new_id} creado para {proveedor_seleccionado}!", icon="📦")
                        st.success("¡Pedido registrado, guardado en .db y enviado a Telegram con éxito!")
                        st.rerun()
                    else:
                        st.warning("Debes ingresar al menos una cantidad en la columna 'PEDIDO' de algún producto.")
                else:
                    st.error("Debes seleccionar un proveedor válido.")

        with tab2:
            st.subheader("📂 Subida y Descarga de Catálogos por Proveedor")
            st.markdown("Sube tu archivo con las columnas: **PROVEEDOR**, **PRODUCTO**, **MINIMO**, **MAXIMO**, **UNIDAD**, **PEDIDO**.")
            
            col_carg, col_desc = st.columns(2)
            
            with col_carg:
                st.markdown("##### 📥 Subir Catálogo (Excel)")
                archivo_excel = st.file_uploader("Sube tu archivo .xlsx", type=["xlsx"], key="up_excel_cat")
                if st.button("Procesar Subida de Catálogo"):
                    if archivo_excel is not None:
                        try:
                            df_subido = pd.read_excel(archivo_excel)
                            df_subido.columns = [str(c).strip().upper() for c in df_subido.columns]
                            
                            if "PROVEEDOR" in df_subido.columns and "PRODUCTO" in df_subido.columns:
                                df_subido["PROVEEDOR"] = df_subido["PROVEEDOR"].ffill()
                                
                                for prov_nombre, grupo in df_subido.groupby("PROVEEDOR"):
                                    if pd.notna(prov_nombre) and str(prov_nombre).strip() != "":
                                        sub_df = grupo[["PRODUCTO", "MINIMO", "MAXIMO", "UNIDAD", "PEDIDO"]].copy()
                                        sub_df = sub_df[sub_df["PRODUCTO"].notna() & (sub_df["PRODUCTO"].astype(str).str.strip() != "")]
                                        for col in ["MINIMO", "MAXIMO", "UNIDAD"]:
                                            if col in sub_df.columns:
                                                sub_df[col] = sub_df[col].astype(str).replace("nan", "")
                                        sub_df["PEDIDO"] = ""
                                        st.session_state.proveedores_catalogo[str(prov_nombre).strip()] = sub_df
                                
                                guardar_datos_locales()
                                st.success("¡Catálogos cargados, agrupados y guardados en la base de datos con éxito!")
                                st.rerun()
                            else:
                                st.error("El archivo Excel debe contener al menos las columnas 'PROVEEDOR' y 'PRODUCTO'.")
                        except Exception as e:
                            st.error(f"Error al procesar el archivo: {e}")

            with col_desc:
                st.markdown("##### 📤 Descargar Catálogo General en Excel")
                if st.session_state.proveedores_catalogo:
                    lista_dfs = []
                    for prov_k, df_val in st.session_state.proveedores_catalogo.items():
                        temp_df = df_val.copy()
                        temp_df.insert(0, "PROVEEDOR", prov_k)
                        lista_dfs.append(temp_df)
                    
                    df_export_final = pd.concat(lista_dfs, ignore_index=True)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_export_final.to_excel(writer, index=False, sheet_name='Catalogos')
                    excel_bytes = output.getvalue()
                    
                    st.download_button(
                        label="📥 Descargar Catálogos (Excel)",
                        data=excel_bytes,
                        file_name=f"Catalogos_Proveedores_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("No hay catálogos disponibles para descargar.")

            st.markdown("---")
            if st.session_state.proveedores_catalogo:
                st.markdown("##### 📋 Visualizar / Gestionar Proveedores Registrados")
                p_sel = st.selectbox("Selecciona proveedor a revisar", list(st.session_state.proveedores_catalogo.keys()), key="ver_prov_cat")
                if p_sel:
                    st.dataframe(st.session_state.proveedores_catalogo[p_sel], use_container_width=True)
                    if st.button("🗑 Eliminar este Proveedor"):
                        del st.session_state.proveedores_catalogo[p_sel]
                        guardar_datos_locales()
                        st.success("Proveedor eliminado y base de datos actualizada.")
                        st.rerun()

        with tab3:
            st.subheader("Historial General de Pedidos")
            if not st.session_state.orders.empty:
                for index, row in st.session_state.orders.iterrows():
                    with st.container():
                        cols = st.columns([0.6, 1.4, 2, 3, 2.5])
                        
                        cols[0].write(f"**#{row['ID']}**")
                        cols[1].write(f"{row['Fecha']}")
                        cols[2].write(f"**PROVEEDOR:** {row['PROVEEDOR']}")
                        
                        # Mostrar limpio en pantalla (solo producto y cantidad)
                        detalle_pantalla = ""
                        for linea in str(row['PRODUCTOS_DETALLE']).split("\n"):
                            if not linea.strip():
                                continue
                            p_v, c_v = "", ""
                            for p_text in linea.split("|"):
                                p_text = p_text.strip()
                                if p_text.startswith("PRODUCTO:"):
                                    p_v = p_text.replace("PRODUCTO:", "").strip()
                                elif p_text.startswith("PEDIDO:"):
                                    c_v = p_text.replace("PEDIDO:", "").strip()
                            if p_v and c_v:
                                detalle_pantalla += f"• {p_v}: {c_v}\n"
                            else:
                                detalle_pantalla += f"• {linea}\n"
                        
                        cols[3].write(detalle_pantalla.strip())
                        
                        estatus_actual = row['Estatus']
                        proveedor_actual = row['PROVEEDOR']
                        
                        if estatus_actual == "Pedido realizado":
                            bg_color = "#E74C3C"
                        elif estatus_actual == "Se mandó a proveedor":
                            bg_color = "#F39C12"
                        else:
                            bg_color = "#27AE60"
                            
                        with cols[4]:
                            # 4 subcolumnas horizontales: Estatus, Cambiar, PDF, Eliminar
                            sub_c1, sub_c2, sub_c3, sub_c4 = st.columns(4)
                            
                            with sub_c1:
                                st.markdown(
                                    f"""
                                    <div class="estatus-badge-horizontal" style="background-color: {bg_color}; color: #FFFFFF;">
                                        {estatus_actual}
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                                
                            with sub_c2:
                                if st.button("🔄 Cambiar", key=f"btn_change_{row['ID']}"):
                                    if estatus_actual == "Pedido realizado":
                                        nuevo = "Se mandó a proveedor"
                                    elif estatus_actual == "Se mandó a proveedor":
                                        nuevo = "Entregado"
                                    else:
                                        nuevo = "Pedido realizado"
                                    
                                    st.session_state.orders.loc[index, "Estatus"] = nuevo
                                    guardar_datos_locales()
                                    
                                    mensaje_telegram = f"Actualización de Pedido\nPROVEEDOR: {proveedor_actual}\nPedido: #{row['ID']}\nNuevo Estatus: {nuevo}"
                                    enviar_alerta_telegram(mensaje_telegram, message_thread_id=TELEGRAM_TOPIC_ESTATUS)
                                    
                                    st.toast(f"📢 Pedido #{row['ID']} actualizado a: {nuevo}", icon="🔄")
                                    st.rerun()
                                    
                            with sub_c3:
                                pdf_buffer = generar_pdf(row['ID'], row['PROVEEDOR'], row['PRODUCTOS_DETALLE'], row['Estatus'], row['Fecha'])
                                st.download_button(
                                    label="📄 PDF",
                                    data=pdf_buffer,
                                    file_name=f"Pedido_{row['ID']}_{row['PROVEEDOR']}.pdf",
                                    mime="application/pdf",
                                    key=f"pdf_{row['ID']}"
                                )

                            with sub_c4:
                                if st.button("🗑️", key=f"btn_delete_{row['ID']}"):
                                    st.session_state.orders = st.session_state.orders.drop(index).reset_index(drop=True)
                                    guardar_datos_locales()
                                    st.toast(f"🗑️ Pedido #{row['ID']} eliminado correctamente.", icon="🗑️")
                                    st.rerun()

                        st.markdown("---")
            else:
                st.info("No hay pedidos registrados en el historial todavía.")

    elif choice == "👥 Administración de Usuarios" and st.session_state.role == "Administrador":
        st.title("👥 Panel de Administración de Usuarios")
        
        user_display = pd.DataFrame([
            {"Usuario": k, "Contraseña": v["password"], "Rol": v["role"]} 
            for k, v in st.session_state.users.items()
        ])
        st.dataframe(user_display, use_container_width=True)
        
        st.subheader("Crear o Editar Usuario")
        with st.form("edit_user_form"):
            u_name = st.text_input("Nombre de Usuario")
            u_pass = st.text_input("Contraseña", type="password")
            u_role = st.selectbox("Rol del Usuario", ["Usuario", "Administrador"])
            save_user = st.form_submit_button("Guardar Usuario")
            
            if save_user and u_name and u_pass:
                st.session_state.users[u_name] = {"password": u_pass, "role": u_role}
                st.success(f"¡El usuario '{u_name}' ha sido guardado con éxito!")
                st.rerun()