from datetime import datetime
import io
import os
import sqlite3
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

# ==========================================
# 0. SISTEMA DE SEGURIDAD Y ACCESO RESTRINGIDO
# ==========================================
st.set_page_config(
    page_title="Vive Más - Sistema de Farmacovigilancia", layout="wide"
)

def verificar_acceso():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
        with col_c2:
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.title("🔒 Acceso Restringido")
            st.subheader("Vive Más: Sistema de Farmacovigilancia")
            st.markdown("Por favor, introduce la clave de acceso autorizada para entrar al sistema.")
            
            clave = st.text_input("Clave de acceso:", type="password", key="input_clave_seguridad")
            if st.button("Ingresar al Sistema"):
                if clave == "Vivemas123":
                    st.session_state["autenticado"] = True
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta. Acceso denegado.")
        return False
    return True

if not verificar_acceso():
    st.stop() # Detiene la ejecución si no está autenticado

# ==========================================
# 1. BASE DE DATOS LOCAL (SQLite)
# ==========================================
def inicializar_bd():
    conn = sqlite3.connect("vive_mas_local.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registros_jornada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            zona TEXT,
            paciente_id TEXT,
            edad INTEGER,
            diagnostico TEXT,
            farmaco_entregado TEXT,
            cantidad_entregada INTEGER,
            sincronizado INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registros_historicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            zona TEXT,
            paciente_id TEXT,
            edad INTEGER,
            diagnostico TEXT,
            farmaco_entregado TEXT,
            cantidad_entregada INTEGER,
            archivo_origen TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE registros_jornada ADD COLUMN sincronizado INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

inicializar_bd()

def conectar_firestore():
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        archivos_json = [f for f in os.listdir(".") if f.endswith(".json")]
        if archivos_json:
            cred = credentials.Certificate(archivos_json[0])
            firebase_admin.initialize_app(cred)
        else:
            return None
    return firestore.client()

# ==========================================
# 2. CONFIGURACIÓN Y ESTILOS VIVE MÁS (UI/UX)
# ==========================================
st.markdown(
    """
    <style>
        :root {
            --primary-blue: #0A2540;
            --accent-blue: #0066CC;
            --soft-bg: #F4F8FB;
            --card-bg: #FFFFFF;
            --text-main: #1A2B3C;
        }

        .main {
            background-color: var(--soft-bg);
            color: var(--text-main);
        }

        h2, h3 {
            color: var(--primary-blue);
            font-family: 'Inter', sans-serif;
        }

        h1 {
            color: var(--primary-blue);
            text-align: center;
            font-family: 'Inter', sans-serif;
            font-weight: 800;
            margin-bottom: 1.5rem;
            font-size: 2.2rem;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            background-color: #E2E8F0;
            padding: 8px;
            border-radius: 12px;
            display: inline-flex;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: transparent;
            border-radius: 8px;
            padding: 8px 18px;
            font-weight: 600;
            color: var(--primary-blue);
            border: none !important;
            transition: all 0.2s ease;
        }

        .stTabs [data-baseweb="tab"]:hover {
            background-color: rgba(255, 255, 255, 0.6);
        }

        .stTabs [aria-selected="true"] {
            background-color: #E0F2FE !important;
            color: #0369A1 !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        .stButton > button, div.stDownloadButton > button {
            display: inline-flex !important;
            width: auto !important;
            min-width: 130px;
            background-color: var(--accent-blue) !important;
            color: white !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            border: none !important;
            padding: 0.45rem 1.2rem !important;
            box-shadow: 0 4px 6px rgba(0, 102, 204, 0.2);
            transition: all 0.3s ease;
        }
        .stButton > button:hover, div.stDownloadButton > button:hover {
            background-color: #004C99 !important;
            color: white !important;
            box-shadow: 0 6px 8px rgba(0, 102, 204, 0.3);
        }
        
        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 1px solid #E2E8F0;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Encabezado
col_l1, col_l2, col_l3 = st.columns([2, 1, 2])
with col_l2:
    if os.path.exists("logo_vive_mas.png.png"):
        st.image("logo_vive_mas.png.png", width=150)
    elif os.path.exists("logo_vive_mas.png"):
        st.image("logo_vive_mas.png", width=150)
    else:
        st.warning("⚠️ Asegúrate de guardar el archivo como 'logo_vive_mas.png.png' en la carpeta.")

st.title("Vive Más: Sistema de Farmacovigilancia")

# Listas base iniciales almacenadas en session_state
if "lista_zonas" not in st.session_state:
    st.session_state["lista_zonas"] = ["La Guaira", "Caracas", "Miranda", "Carabobo", "Zulia", "Catia la Mar"]

if "lista_farmacos" not in st.session_state:
    st.session_state["lista_farmacos"] = [
        "Paracetamol 500mg", "Ibuprofeno 400mg", "Amoxicilina 500mg", 
        "Omeprazol 20mg", "Losartán Potásico 50mg", "Diclofenaco Sódico 75mg/3ml", 
        "Amlodipina 5.0mg", "Metformina 850mg", "Loratadina 10mg", "Suero Oral"
    ]

# ==========================================
# BARRA LATERAL
# ==========================================
with st.sidebar:
    st.header("⚙️ Configuración")
    with st.expander("🛠️ Ajustes del Sistema", expanded=False):
        api_key = st.text_input("Gemini API Key", type="password", key="api_key_input")

    api_key_val = api_key if 'api_key' in locals() else ""

    st.divider()

    st.header("🌐 Sincronización Cloud")
    if st.button("🔄 Sincronizar Pendientes a Firebase"):
        with st.spinner("Conectando con Firebase..."):
            try:
                db_cloud = conectar_firestore()
                if not db_cloud:
                    st.error("No se encontró el archivo JSON de credenciales.")
                else:
                    conn = sqlite3.connect("vive_mas_local.db")
                    df_pendientes = pd.read_sql("SELECT id, fecha, zona, paciente_id, edad, diagnostico, farmaco_entregado, cantidad_entregada FROM registros_jornada WHERE sincronizado = 0", conn)
                    if df_pendientes.empty:
                        st.info("No hay registros pendientes.")
                        conn.close()
                    else:
                        exitosos = 0
                        cursor = conn.cursor()
                        for _, row in df_pendientes.iterrows():
                            data_dict = {
                                "fecha": row["fecha"],
                                "zona": row["zona"],
                                "paciente_id": row["paciente_id"],
                                "edad": int(row["edad"]),
                                "diagnostico": row["diagnostico"],
                                "farmaco_entregado": row["farmaco_entregado"],
                                "cantidad_entregada": int(row["cantidad_entregada"]),
                                "sincronizado_en": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            db_cloud.collection("registros_jornada").add(data_dict)
                            cursor.execute("UPDATE registros_jornada SET sincronizado = 1 WHERE id = ?", (row["id"],))
                            conn.commit()
                            exitosos += 1
                        conn.close()
                        st.success(f"¡Sincronizados {exitosos} registros!")
                        st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# ==========================================
# PESTAÑAS PRINCIPALES
# ==========================================
tab_reg, tab_stock, tab_hist, tab_audit, tab_reportes = st.tabs([
    "📝 Registro Local",
    "📦 Control de Stock",
    "📁 Jornadas Anteriores",
    "🧠 Auditoría Inteligente con IA",
    "📊 Reportes y Nube"
])

# ------------------------------------------
# MÓDULO 1: REGISTRO LOCAL
# ------------------------------------------
with tab_reg:
    st.subheader("Libreta de Atención Diaria")
    
    opciones_zona_form = ["➕ Agregar nuevo lugar..."] + st.session_state["lista_zonas"]
    zona_elegida_form = st.selectbox("Selecciona la Zona de Atención para este registro", options=opciones_zona_form, key="select_zona_main")
    
    zona_final_registro = "La Guaira"
    if zona_elegida_form == "➕ Agregar nuevo lugar...":
        nueva_zona_form = st.text_input("✍️ Escribe el nombre del nuevo lugar:", key="input_nueva_zona")
        if nueva_zona_form:
            zona_final_registro = nueva_zona_form
            if nueva_zona_form not in st.session_state["lista_zonas"]:
                st.session_state["lista_zonas"].append(nueva_zona_form)
        else:
            zona_final_registro = ""
    else:
        zona_final_registro = zona_elegida_form

    st.info(f"📍 Zona activa seleccionada: **{zona_final_registro if zona_final_registro else 'Escribe un lugar válido'}**")

    with st.form("form_atencion", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            paciente_id = st.text_input("ID o Nombre del Paciente")
            edad = st.number_input("Edad", min_value=0, max_value=120, value=30)
            diagnostico = st.text_input("Diagnóstico Clínico")
        with col_b:
            opciones_farmacos_form = ["➕ Agregar nuevo medicamento..."] + st.session_state["lista_farmacos"]
            farmaco_elegido_form = st.selectbox("Fármaco Entregado", options=opciones_farmacos_form, key="select_farmaco_main")
            
            nuevo_farmaco_form = ""
            if farmaco_elegido_form == "➕ Agregar nuevo medicamento...":
                nuevo_farmaco_form = st.text_input("✍️ Escribe el nombre y dosis del nuevo fármaco:", key="input_nuevo_farmaco")

            cantidad = st.number_input("Cantidad Entregada", min_value=1, value=30)
        
        submitted = st.form_submit_button("💾 Guardar Atención Localmente")
        if submitted:
            farmaco_final = nuevo_farmaco_form if farmaco_elegido_form == "➕ Agregar nuevo medicamento..." else farmaco_elegido_form
            
            if not zona_final_registro:
                st.error("Por favor escribe el nombre del nuevo lugar.")
            elif farmaco_elegido_form == "➕ Agregar nuevo medicamento..." and not nuevo_farmaco_form:
                st.error("Por favor escribe el nombre del nuevo medicamento.")
            elif paciente_id and farmaco_final:
                if farmaco_final not in st.session_state["lista_farmacos"]:
                    st.session_state["lista_farmacos"].append(farmaco_final)

                conn = sqlite3.connect("vive_mas_local.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO registros_jornada (fecha, zona, paciente_id, edad, diagnostico, farmaco_entregado, cantidad_entregada, sincronizado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """, (datetime.now().strftime("%Y-%m-%d"), zona_final_registro, paciente_id, edad, diagnostico, farmaco_final, cantidad))
                conn.commit()
                conn.close()
                st.success(f"¡Atención de {paciente_id} guardada con éxito en {zona_final_registro}!")
            else:
                st.error("Por favor completa al menos el ID del paciente y el fármaco.")

    st.divider()
    conn = sqlite3.connect("vive_mas_local.db")
    df_local = pd.read_sql("SELECT * FROM registros_jornada", conn)
    conn.close()
    
    if not df_local.empty:
        st.dataframe(df_local, use_container_width=True)
        
        col_dl, col_del = st.columns(2)
        with col_dl:
            buffer_local = io.BytesIO()
            with pd.ExcelWriter(buffer_local, engine="openpyxl") as writer:
                df_local.to_excel(writer, index=False, sheet_name="Registros_Locales")
            st.download_button(
                label="📥 Descargar Registros Locales en Excel",
                data=buffer_local.getvalue(),
                file_name="Registros_Locales_ViveMas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col_del:
            if st.button("🗑️ Borrar Base de Datos Local"):
                conn = sqlite3.connect("vive_mas_local.db")
                conn.cursor().execute("DELETE FROM registros_jornada")
                conn.commit()
                conn.close()
                st.rerun()

# ------------------------------------------
# MÓDULO 2: CONTROL DE STOCK
# ------------------------------------------
with tab_stock:
    st.subheader("📦 Control y Análisis de Stock Post-Jornada")
    st.markdown("Adjunta uno o varios archivos Excel/CSV con el **Stock Inicial** y archivos con el **Stock Final** para comparar lo que había, lo que se usó y detectar alertas de escasez.")

    col_st1, col_st2 = st.columns(2)
    with col_st1:
        archivos_iniciales = st.file_uploader("📁 Adjuntar Stock Inicial (Excel / CSV)", type=["xlsx", "csv"], accept_multiple_files=True, key="up_inicial")
    with col_st2:
        archivos_finales = st.file_uploader("📁 Adjuntar Stock Final / Remanente (Excel / CSV)", type=["xlsx", "csv"], accept_multiple_files=True, key="up_final")

    df_inicial_total = pd.DataFrame()
    df_final_total = pd.DataFrame()

    if archivos_iniciales:
        lista_i = []
        for arch in archivos_iniciales:
            df_i = pd.read_csv(arch) if arch.name.endswith(".csv") else pd.read_excel(arch)
            df_i.columns = df_i.columns.str.strip()
            lista_i.append(df_i)
        if lista_i:
            df_inicial_total = pd.concat(lista_i, ignore_index=True)

    if archivos_finales:
        lista_f = []
        for arch in archivos_finales:
            df_f = pd.read_csv(arch) if arch.name.endswith(".csv") else pd.read_excel(arch)
            df_f.columns = df_f.columns.str.strip()
            lista_f.append(df_f)
        if lista_f:
            df_final_total = pd.concat(lista_f, ignore_index=True)

    if not df_inicial_total.empty and not df_final_total.empty:
        col_f_i = next((c for c in df_inicial_total.columns if "farmaco" in c.lower() or "fármaco" in c.lower() or "producto" in c.lower()), df_inicial_total.columns[0])
        col_c_i = next((c for c in df_inicial_total.columns if "stock" in c.lower() or "cantidad" in c.lower() or "inicial" in c.lower() or "actual" in c.lower()), df_inicial_total.columns[1])

        col_f_f = next((c for c in df_final_total.columns if "farmaco" in c.lower() or "fármaco" in c.lower() or "producto" in c.lower()), df_final_total.columns[0])
        col_c_f = next((c for c in df_final_total.columns if "stock" in c.lower() or "cantidad" in c.lower() or "final" in c.lower() or "remanente" in c.lower()), df_final_total.columns[1])

        df_i_grouped = df_inicial_total.groupby(col_f_i)[col_c_i].sum().reset_index()
        df_i_grouped.columns = ["Fármaco", "Stock_Inicial"]

        df_f_grouped = df_final_total.groupby(col_f_f)[col_c_f].sum().reset_index()
        df_f_grouped.columns = ["Fármaco", "Stock_Final"]

        df_stock_resumen = pd.merge(df_i_grouped, df_f_grouped, on="Fármaco", how="outer").fillna(0)
        df_stock_resumen["Cantidad_Usada"] = df_stock_resumen["Stock_Inicial"] - df_stock_resumen["Stock_Final"]

        st.divider()
        st.subheader("📋 Cuadro Comparativo de Inventario y Consumo")
        st.markdown("💡 *Los medicamentos con stock final bajo ($\le 5$ unidades) se sombrean automáticamente en rojo.*")

        def resaltar_stock_critico(row):
            color = 'background-color: #FFC7CE; color: #9C0006;' if row["Stock_Final"] <= 5 else ''
            return [color] * len(row)

        df_estilizado = df_stock_resumen.style.apply(resaltar_stock_critico, axis=1)
        st.dataframe(df_estilizado, use_container_width=True)

        buffer_stock = io.BytesIO()
        with pd.ExcelWriter(buffer_stock, engine="openpyxl") as writer:
            df_stock_resumen.to_excel(writer, index=False, sheet_name="Control_Stock")
        st.download_button(
            label="📥 Descargar Reporte de Stock en Excel",
            data=buffer_stock.getvalue(),
            file_name="Reporte_Control_Stock.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("👆 Por favor adjunta tanto el archivo de **Stock Inicial** como el de **Stock Final** para generar la tabla comparativa.")

# ------------------------------------------
# MÓDULO 3: JORNADAS ANTERIORES
# ------------------------------------------
with tab_hist:
    st.subheader("📁 Carga y Gestión de Jornadas Anteriores")
    st.markdown("Sube aquí tus archivos Excel o CSV de jornadas pasadas para agregarlos al sistema, guardarlos localmente o subirlos a la nube.")

    archivos_historicos = st.file_uploader("Subir archivos Excel/CSV históricos", type=["xlsx", "csv"], accept_multiple_files=True, key="upload_hist_tab")
    
    if archivos_historicos:
        lista_dfs = []
        for arch in archivos_historicos:
            df_h = pd.read_csv(arch) if arch.name.endswith(".csv") else pd.read_excel(arch)
            df_h.columns = df_h.columns.str.strip()
            df_h["archivo_origen"] = arch.name
            lista_dfs.append(df_h)
        if lista_dfs:
            df_historico_acumulado = pd.concat(lista_dfs, ignore_index=True)
            st.session_state["df_historico"] = df_historico_acumulado
            st.success(f"¡{len(archivos_historicos)} archivo(s) cargado(s) en memoria correctamente!")
            st.dataframe(df_historico_acumulado, use_container_width=True)

            col_hb1, col_hb2 = st.columns(2)
            with col_hb1:
                if st.button("💾 Guardar Registros Históricos Localmente"):
                    try:
                        conn_l = sqlite3.connect("vive_mas_local.db")
                        cursor_l = conn_l.cursor()
                        guardados_loc = 0
                        for _, row in df_historico_acumulado.iterrows():
                            p_id = row.get("paciente_id", row.get("Paciente", "Desconocido"))
                            p_id = "Desconocido" if pd.isna(p_id) else str(p_id)
                            
                            edad_val = row.get("edad", row.get("Edad", 0))
                            edad_val = 0 if pd.isna(edad_val) else int(edad_val)
                            
                            diag_val = row.get("diagnostico", row.get("Diagnostico", "N/A"))
                            diag_val = "N/A" if pd.isna(diag_val) else str(diag_val)
                            
                            farm_val = row.get("farmaco_entregado", row.get("Farmaco", "N/A"))
                            farm_val = "N/A" if pd.isna(farm_val) else str(farm_val)
                            
                            cant_val = row.get("cantidad_entregada", row.get("Cantidad", 1))
                            cant_val = 1 if pd.isna(cant_val) else int(cant_val)

                            fec_val = row.get("fecha", row.get("Fecha", datetime.now().strftime("%Y-%m-%d")))
                            fec_val = datetime.now().strftime("%Y-%m-%d") if pd.isna(fec_val) else str(fec_val)

                            zon_val = row.get("zona", row.get("Zona", "La Guaira"))
                            zon_val = "La Guaira" if pd.isna(zon_val) else str(zon_val)

                            cursor_l.execute("""
                                INSERT INTO registros_historicos (fecha, zona, paciente_id, edad, diagnostico, farmaco_entregado, cantidad_entregada, archivo_origen)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (fec_val, zon_val, p_id, edad_val, diag_val, farm_val, cant_val, str(row.get("archivo_origen", "excel"))))
                            guardados_loc += 1
                        conn_l.commit()
                        conn_l.close()
                        st.success(f"¡{guardados_loc} registros guardados localmente con fecha y zona!")
                    except Exception as err_loc:
                        st.error(f"Error al guardar: {err_loc}")

            with col_hb2:
                if st.button("☁️ Subir Registros Históricos a Firebase"):
                    with st.spinner("Subiendo registros históricos a la nube..."):
                        try:
                            db_cloud_h = conectar_firestore()
                            if not db_cloud_h:
                                st.error("No se encontró el archivo JSON de credenciales de Firebase.")
                            else:
                                subidos_nube = 0
                                for _, row in df_historico_acumulado.iterrows():
                                    p_id = row.get("paciente_id", row.get("Paciente", "Histórico"))
                                    p_id = "Histórico" if pd.isna(p_id) else str(p_id)
                                    
                                    edad_val = row.get("edad", row.get("Edad", 30))
                                    edad_val = 30 if pd.isna(edad_val) else int(edad_val)
                                    
                                    diag_val = row.get("diagnostico", row.get("Diagnostico", "Histórico"))
                                    diag_val = "Histórico" if pd.isna(diag_val) else str(diag_val)
                                    
                                    farm_val = row.get("farmaco_entregado", row.get("Farmaco", "N/A"))
                                    farm_val = "N/A" if pd.isna(farm_val) else str(farm_val)
                                    
                                    cant_val = row.get("cantidad_entregada", row.get("Cantidad", 1))
                                    cant_val = 1 if pd.isna(cant_val) else int(cant_val)

                                    fec_val = row.get("fecha", row.get("Fecha", datetime.now().strftime("%Y-%m-%d")))
                                    fec_val = datetime.now().strftime("%Y-%m-%d") if pd.isna(fec_val) else str(fec_val)

                                    zon_val = row.get("zona", row.get("Zona", "La Guaira"))
                                    zon_val = "La Guaira" if pd.isna(zon_val) else str(zon_val)

                                    data_h = {
                                        "fecha": fec_val,
                                        "zona": zon_val,
                                        "paciente_id": p_id,
                                        "edad": edad_val,
                                        "diagnostico": diag_val,
                                        "farmaco_entregado": farm_val,
                                        "cantidad_entregada": cant_val,
                                        "tipo_registro": "historico_excel",
                                        "sincronizado_en": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                    db_cloud_h.collection("registros_jornada").add(data_h)
                                    subidos_nube += 1
                                st.success(f"¡{subidos_nube} registros subidos a Firebase correctamente!")
                        except Exception as err_nube:
                            st.error(f"Error en Firebase: {err_nube}")
    else:
        st.info("👆 Sube archivos en formato Excel o CSV para comenzar a gestionar jornadas anteriores.")

# ------------------------------------------
# MÓDULO 4: AUDITORÍA INTELIGENTE CON FILTROS DE PRECISIÓN ABSOLUTA
# ------------------------------------------
with tab_audit:
    st.subheader("🧠 Auditoría Inteligente y Razonamiento Clínico")
    st.markdown(
        "Asistente analítico inteligente con filtros estrictos de precisión para responder exactamente lo que pides (más frecuente, menos frecuente, por zona, etc.)."
    )

    col_btn1, col_btn2 = st.columns([1, 2])
    with col_btn1:
        if st.button("☁️ Sincronizar y Cargar Datos de la Nube para Análisis"):
            with st.spinner("Descargando datos desde Firebase..."):
                try:
                    db_cloud = conectar_firestore()
                    if not db_cloud:
                        st.error("No se encontró el archivo JSON de credenciales de Firebase.")
                    else:
                        docs = db_cloud.collection("registros_jornada").stream()
                        lista_docs = [doc.to_dict() for doc in docs]
                        if lista_docs:
                            st.session_state["df_nube_audit"] = pd.DataFrame(lista_docs)
                            st.success(f"¡{len(lista_docs)} registros cargados y listos!")
                        else:
                            st.warning("La base de datos en Firebase está vacía.")
                except Exception as e:
                    st.error(f"Error al conectar con la nube: {e}")

    if "messages_nube" not in st.session_state:
        st.session_state.messages_nube = []

    for message in st.session_state.messages_nube:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt_usuario := st.chat_input("Escribe tu pregunta analítica (Ej: ¿Cuál es la enfermedad menos frecuente?)..."):
        st.session_state.messages_nube.append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"):
            st.markdown(prompt_usuario)

        with st.chat_message("assistant"):
            with st.spinner("Analizando con precisión milimétrica..."):
                df_nube_data = st.session_state.get("df_nube_audit", pd.DataFrame())
                
                resultado_analisis = ""
                
                if df_nube_data.empty:
                    resultado_analisis = "⚠️ Primero haz clic en el botón **'Sincronizar y Cargar Datos de la Nube para Análisis'**."
                else:
                    q_lower = prompt_usuario.lower()
                    
                    # Detección de zona específica
                    zonas_disp = df_nube_data["zona"].dropna().unique().tolist() if "zona" in df_nube_data.columns else []
                    zona_m = next((z for z in zonas_disp if z.lower() in q_lower), None)
                    df_f = df_nube_data[df_nube_data["zona"].str.lower() == zona_m.lower()] if zona_m and "zona" in df_nube_data.columns else df_nube_data
                    
                    etiqueta_zona = f" en la zona **{zona_m}**" if zona_m else " (General de todas las zonas)"
                    
                    # 1. Análisis de Medicamentos / Fármacos
                    if any(w in q_lower for w in ["medicamento", "fármaco", "farmaco", "abundancia", "mas hay", "más hay", "stock", "entregado", "usado"]):
                        if "farmaco_entregado" in df_f.columns and "cantidad_entregada" in df_f.columns:
                            top_f = df_f.groupby("farmaco_entregado")["cantidad_entregada"].sum().reset_index().sort_values(by="cantidad_entregada", ascending=False)
                            
                            resultado_analisis += f"📊 **Análisis de Fármacos{etiqueta_zona}:**\n\n"
                            if not top_f.empty:
                                if "menos" in q_lower or "baja" in q_lower:
                                    objetivo = top_f.iloc[-1]
                                    resultado_analisis += f"- 📉 **Medicamento con menor entrega:** **{objetivo['farmaco_entregado']}** con **{objetivo['cantidad_entregada']} unidades**.\n"
                                else:
                                    objetivo = top_f.iloc[0]
                                    resultado_analisis += f"- 🥇 **Medicamento con mayor entrega / abundancia:** **{objetivo['farmaco_entregado']}** con **{objetivo['cantidad_entregada']} unidades**.\n"
                                
                                resultado_analisis += "\n**Ranking completo:**\n"
                                for _, r in top_f.iterrows():
                                    resultado_analisis += f"  - {r['farmaco_entregado']}: {r['cantidad_entregada']} u.\n"
                            else:
                                resultado_analisis += "No hay registros.\n"
                    
                    # 2. Análisis de Diagnósticos / Enfermedades
                    elif any(w in q_lower for w in ["enfermedad", "diagnostico", "diagnóstico", "frecuente", "caso"]):
                        if "diagnostico" in df_f.columns:
                            df_diag_limpio = df_f[df_f["diagnostico"].notna()].copy()
                            df_diag_limpio["diagnostico_str"] = df_diag_limpio["diagnostico"].astype(str).str.strip()
                            
                            # Excluir etiquetas basura o de importación histórica
                            exclusiones = ["histórico", "historico", "n/a", "desconocido", "****", ""]
                            df_diag_limpio = df_diag_limpio[~df_diag_limpio["diagnostico_str"].str.lower().isin(exclusiones)]
                            
                            top_d = df_diag_limpio["diagnostico_str"].value_counts().reset_index()
                            top_d.columns = ["Diagnóstico", "Casos"]
                            
                            resultado_analisis += f"🩺 **Diagnósticos y Enfermedades{etiqueta_zona}:**\n\n"
                            if not top_d.empty:
                                if "menos" in q_lower:
                                    objetivo_d = top_d.iloc[-1]
                                    resultado_analisis += f"- 📉 **Enfermedad menos frecuente:** **{objetivo_d['Diagnóstico']}** con **{objetivo_d['Casos']} casos** registrados.\n\n"
                                else:
                                    objetivo_d = top_d.iloc[0]
                                    resultado_analisis += f"- 🏆 **Enfermedad más frecuente:** **{objetivo_d['Diagnóstico']}** con **{objetivo_d['Casos']} casos** registrados.\n\n"
                                
                                resultado_analisis += "**Listado general:**\n"
                                for _, rd in top_d.iterrows():
                                    resultado_analisis += f"  - {rd['Diagnóstico']}: {rd['Casos']} casos\n"
                            else:
                                resultado_analisis += "No hay diagnósticos válidos registrados.\n"
                    
                    # 3. Consulta General
                    else:
                        total_pacientes = len(df_f)
                        resultado_analisis += f"📋 **Resumen General de la Información{etiqueta_zona}:**\n"
                        resultado_analisis += f"- Total de atenciones analizadas: {total_pacientes}\n\n"

                # Intento opcional con Gemini si hay API Key
                if api_key_val and not df_nube_data.empty:
                    try:
                        client = genai.Client(api_key=api_key_val, http_options=types.HttpOptions(timeout=15.0))
                        prompt_ia = f"Basándote en estos datos médicos: {df_nube_data.to_json(orient='records')}, responde con absoluta precisión a la pregunta: '{prompt_usuario}'. Sé directo y exacto."
                        resp_ai = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_ia)
                        if resp_ai and resp_ai.text:
                            resultado_analisis = resp_ai.text
                    except Exception:
                        pass

                st.markdown(resultado_analisis)
                st.session_state.messages_nube.append({"role": "assistant", "content": resultado_analisis})

# ------------------------------------------
# MÓDULO 5: REPORTES Y VISOR HISTÓRICO
# ------------------------------------------
with tab_reportes:
    st.subheader("📊 Reportes y Registros Históricos Guardados Localmente")
    st.markdown("Visualiza los registros de jornadas anteriores guardados localmente especificando su **Fecha** y **Zona**.")

    conn = sqlite3.connect("vive_mas_local.db")
    df_ver_historico = pd.read_sql("SELECT fecha, zona, paciente_id, edad, diagnostico, farmaco_entregado, cantidad_entregada, archivo_origen FROM registros_historicos", conn)
    conn.close()

    if not df_ver_historico.empty:
        st.success(f"Se encontraron **{len(df_ver_historico)}** registros históricos almacenados localmente.")
        
        col_rf1, col_rf2 = st.columns(2)
        with col_rf1:
            zonas_hist = ["Todas"] + sorted(df_ver_historico["zona"].dropna().unique().tolist())
            zona_hist_sel = st.selectbox("📍 Filtrar Historial por Zona", options=zonas_hist)
        with col_rf2:
            fechas_hist = ["Todas"] + sorted(df_ver_historico["fecha"].dropna().unique().tolist(), reverse=True)
            fecha_hist_sel = st.selectbox("📅 Filtrar Historial por Fecha", options=fechas_hist)

        df_hist_filtrado = df_ver_historico.copy()
        if zona_hist_sel != "Todas":
            df_hist_filtrado = df_hist_filtrado[df_hist_filtrado["zona"] == zona_hist_sel]
        if fecha_hist_sel != "Todas":
            df_hist_filtrado = df_hist_filtrado[df_hist_filtrado["fecha"] == fecha_hist_sel]

        st.dataframe(df_hist_filtrado, use_container_width=True)

        if st.button("🗑️ Borrar Historial Local Guardado"):
            conn = sqlite3.connect("vive_mas_local.db")
            conn.cursor().execute("DELETE FROM registros_historicos")
            conn.commit()
            conn.close()
            st.rerun()
    else:
        st.info("Aún no hay registros históricos guardados localmente.")

    st.divider()
    st.subheader("☁️ Reportes desde Firebase (Nube)")
    if st.button("Cargar Datos de la Nube"):
        db_cloud = conectar_firestore()
        if db_cloud:
            docs = db_cloud.collection("registros_jornada").stream()
            lista_docs = [doc.to_dict() for doc in docs]
            if lista_docs:
                st.session_state["df_nube"] = pd.DataFrame(lista_docs)
                st.success(f"Cargados {len(lista_docs)} registros de la nube.")

    if "df_nube" in st.session_state and not st.session_state["df_nube"].empty:
        df_nube = st.session_state["df_nube"]
        st.dataframe(df_nube, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_nube.to_excel(writer, index=False, sheet_name="Reporte_General")
        st.download_button("📥 Descargar Reporte en Excel", data=buffer.getvalue(), file_name="Reporte_General.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")