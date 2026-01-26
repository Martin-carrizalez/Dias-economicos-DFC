import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import io

st.set_page_config(page_title="Sistema Días Económicos", page_icon="📅", layout="wide")

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

NORMATIVA = {
    'economico': {
        'nombre': 'Día Económico', 
        'max_dias': 3, 
        'max_ocasiones': 3, 
        'intervalo_dias': 30, 
        'descripcion': 'Hasta 3 ocasiones por año',
        'limite': '3 ocasiones/año'
    },
    'matrimonio': {
        'nombre': 'Matrimonio', 
        'max_dias': 10, 
        'max_ocasiones': 1, 
        'descripcion': 'Por una sola ocasión en la vida',
        'limite': '1 vez en la vida'
    },
    'fallecimiento': {
        'nombre': 'Fallecimiento/Enfermedad Grave', 
        'max_dias': 5, 
        'descripcion': 'Parientes primer grado',
        'limite': 'Sin límite'
    },
    'jubilacion': {
        'nombre': 'Trámites Jubilación', 
        'max_dias': 2, 
        'descripcion': 'Solo cuando se jubila',
        'limite': '1 vez en la vida'
    },
    'examen': {
        'nombre': 'Examen Profesional/Tesis', 
        'max_dias': 3, 
        'descripcion': 'Presentación de grado',
        'limite': 'Máximo 3 veces'
    },
    'mudanza': {
        'nombre': 'Cambio de Domicilio', 
        'max_dias': 1, 
        'descripcion': 'Para mudanza',
        'limite': '2 veces/año'
    }
}

def conectar_sheets():
    try:
        creds = Credentials.from_service_account_info(st.secrets["google_sheets"], scopes=SCOPES)
        return gspread.authorize(creds)
    except:
        return None

def verificar_login(usuario, password):
    try:
        usuarios = st.secrets["usuarios"]
        if usuario in usuarios and usuarios[usuario]["password"] == password:
            return True, usuarios[usuario]["nombre"]
    except:
        pass
    return False, None

def inicializar_sheets(client):
    try:
        spreadsheet = client.open("Dias_Economicos_Formacion_Continua")
        sheet_empleados = spreadsheet.worksheet("Empleados")
        sheet_solicitudes = spreadsheet.worksheet("Solicitudes")
        return spreadsheet, sheet_empleados, sheet_solicitudes
    except:
        return None, None, None

def cargar_datos_con_calculo(sheet_emp, sheet_sol):
    """Carga datos y CALCULA días disponibles en tiempo real"""
    df_emp = pd.DataFrame(sheet_emp.get_all_records())
    df_sol = pd.DataFrame(sheet_sol.get_all_records())
    
    # CALCULAR DÍAS DISPONIBLES REALES
    for idx, emp in df_emp.iterrows():
        emp_id = emp['ID']
        
        # Contar días económicos usados este año
        solicitudes_emp = df_sol[
            (df_sol['EmpleadoID'] == emp_id) & 
            (df_sol['Tipo Permiso'] == 'economico')
        ]
        
        dias_usados = 0
        if len(solicitudes_emp) > 0:
            solicitudes_emp['Fecha_Reg'] = pd.to_datetime(solicitudes_emp['Fecha Registro'], errors='coerce')
            solicitudes_año = solicitudes_emp[solicitudes_emp['Fecha_Reg'].dt.year == datetime.now().year]
            dias_usados = int(solicitudes_año['Dias Solicitados'].sum())
        
        df_emp.at[idx, 'DIAS_REALES'] = 9 - dias_usados
    
    return df_emp, df_sol

def validar_solicitud(emp_id, tipo, dias, fecha_inicio, df_emp, df_sol):
    """Validación completa de solicitud"""
    errores = []
    advertencias = []
    
    emp_info = df_emp[df_emp['ID'] == emp_id].iloc[0]
    dias_disponibles = int(emp_info['DIAS_REALES'])
    config = NORMATIVA[tipo]
    
    # Validar días máximos
    if dias > config['max_dias']:
        errores.append(f"❌ Máximo permitido: {config['max_dias']} días")
    
    if tipo == 'economico':
        # Validar días disponibles
        if dias > dias_disponibles:
            errores.append(f"❌ Solo tiene {dias_disponibles} días disponibles (solicitó {dias})")
        
        # Validar ocasiones en el año
        año_actual = datetime.now().year
        solicitudes_eco = df_sol[
            (df_sol['EmpleadoID'] == emp_id) &
            (df_sol['Tipo Permiso'] == 'economico')
        ]
        
        if len(solicitudes_eco) > 0:
            solicitudes_eco['Fecha_Reg'] = pd.to_datetime(solicitudes_eco['Fecha Registro'], errors='coerce')
            solicitudes_año = solicitudes_eco[solicitudes_eco['Fecha_Reg'].dt.year == año_actual]
            
            if len(solicitudes_año) >= config['max_ocasiones']:
                errores.append(f"❌ Ya alcanzó el límite de {config['max_ocasiones']} ocasiones en el año")
            
            # Validar intervalo 30 días
            if len(solicitudes_eco) > 0:
                solicitudes_eco['Fecha_Fin'] = pd.to_datetime(solicitudes_eco['Fecha Fin'], errors='coerce')
                ultima_fecha_fin = solicitudes_eco['Fecha_Fin'].max()
                fecha_inicio_dt = pd.to_datetime(fecha_inicio)
                dias_diferencia = (fecha_inicio_dt - ultima_fecha_fin).days
                
                if dias_diferencia < 30:
                    fecha_valida = ultima_fecha_fin + timedelta(days=30)
                    errores.append(
                        f"❌ Debe esperar {30 - dias_diferencia} días más\n"
                        f"   Último día usado: {ultima_fecha_fin.strftime('%d/%m/%Y')}\n"
                        f"   Puede solicitar desde: {fecha_valida.strftime('%d/%m/%Y')}"
                    )
        
        # Advertencia
        if dias_disponibles - dias <= 2 and dias <= dias_disponibles:
            advertencias.append(f"⚠️ Después quedarán {dias_disponibles - dias} días disponibles")
    
    # Matrimonio solo una vez EN LA VIDA
    if tipo == 'matrimonio':
        solicitudes_mat = df_sol[
            (df_sol['EmpleadoID'] == emp_id) &
            (df_sol['Tipo Permiso'] == 'matrimonio')
        ]
        if len(solicitudes_mat) > 0:
            errores.append("❌ La licencia por matrimonio solo se otorga UNA VEZ en la vida")
    
    # Jubilación solo una vez EN LA VIDA
    if tipo == 'jubilacion':
        solicitudes_jub = df_sol[
            (df_sol['EmpleadoID'] == emp_id) &
            (df_sol['Tipo Permiso'] == 'jubilacion')
        ]
        if len(solicitudes_jub) > 0:
            errores.append("❌ La licencia por jubilación solo se otorga UNA VEZ (cuando se jubila)")
    
    # Examen profesional: máximo 3 veces en la vida (licenciatura, maestría, doctorado)
    if tipo == 'examen':
        solicitudes_exam = df_sol[
            (df_sol['EmpleadoID'] == emp_id) &
            (df_sol['Tipo Permiso'] == 'examen')
        ]
        if len(solicitudes_exam) >= 3:
            errores.append("❌ La licencia por examen profesional se otorga máximo 3 veces (licenciatura, maestría, doctorado)")
    
    # Mudanza: máximo 2 veces por año (razonable)
    if tipo == 'mudanza':
        año_actual = datetime.now().year
        solicitudes_mud = df_sol[
            (df_sol['EmpleadoID'] == emp_id) &
            (df_sol['Tipo Permiso'] == 'mudanza')
        ]
        if len(solicitudes_mud) > 0:
            solicitudes_mud['Fecha_Reg'] = pd.to_datetime(solicitudes_mud['Fecha Registro'], errors='coerce')
            solicitudes_año = solicitudes_mud[solicitudes_mud['Fecha_Reg'].dt.year == año_actual]
            if len(solicitudes_año) >= 2:
                errores.append("❌ La licencia por mudanza se otorga máximo 2 veces por año")
    
    return errores, advertencias

def generar_alertas(df_empleados):
    """Genera alertas de empleados con pocos días"""
    alertas = []
    for _, emp in df_empleados.iterrows():
        dias = int(emp['DIAS_REALES'])
        nombre = f"{emp['PATERNO']} {emp['MATERNO']} {emp['NOMBRE']}"
        
        if dias == 0:
            alertas.append({'tipo': 'error', 'mensaje': f"🚫 {nombre} NO tiene días disponibles"})
        elif dias == 1:
            alertas.append({'tipo': 'warning', 'mensaje': f"⚠️ {nombre} tiene solo 1 día disponible"})
        elif dias <= 3:
            alertas.append({'tipo': 'info', 'mensaje': f"ℹ️ {nombre} tiene {dias} días disponibles"})
    
    return alertas

# ============= LOGIN =============
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 Sistema de Gestión de Días Económicos")
    st.markdown("**Dirección de Formación Continua** - Secretaría de Educación Jalisco")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.subheader("Iniciar Sesión")
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar", use_container_width=True, type="primary"):
            valido, nombre = verificar_login(usuario, password)
            if valido:
                st.session_state['logged_in'] = True
                st.session_state['usuario'] = usuario
                st.session_state['nombre_usuario'] = nombre
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos")
    st.stop()

# ============= MAIN APP =============
st.title("📅 Sistema de Gestión de Días Económicos")
st.markdown("**Dirección de Formación Continua** - Secretaría de Educación Jalisco")

col1, col2 = st.columns([4,1])
with col2:
    st.write(f"👤 **{st.session_state['nombre_usuario']}**")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

st.markdown("---")

# Conectar
client = conectar_sheets()
if not client:
    st.error("⚠️ No se pudo conectar a Google Sheets")
    st.stop()

spreadsheet, sheet_emp, sheet_sol = inicializar_sheets(client)
if not spreadsheet:
    st.error("No se pudieron inicializar las hojas")
    st.stop()

# Cargar datos
df_empleados, df_solicitudes = cargar_datos_con_calculo(sheet_emp, sheet_sol)

# SIDEBAR: Alertas
with st.sidebar:
    st.header("🔔 Alertas y Notificaciones")
    
    if len(df_empleados) > 0:
        alertas = generar_alertas(df_empleados)
        
        if alertas:
            for alerta in alertas:
                if alerta['tipo'] == 'error':
                    st.error(alerta['mensaje'])
                elif alerta['tipo'] == 'warning':
                    st.warning(alerta['mensaje'])
                else:
                    st.info(alerta['mensaje'])
        else:
            st.success("✅ No hay alertas pendientes")
    
    st.markdown("---")
    st.markdown("**📊 Resumen General**")
    if len(df_empleados) > 0:
        st.metric("Total Empleados", len(df_empleados))
        st.metric("Solicitudes Registradas", len(df_solicitudes))
        dias_promedio = df_empleados['DIAS_REALES'].mean()
        st.metric("Días Disponibles (Promedio)", f"{dias_promedio:.1f}")

# TABS PRINCIPALES
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 Registrar Solicitud",
    "👥 Ver Empleados", 
    "📊 Estatus Individual",
    "📄 Reportes",
    "📋 Normativa"
])

# TAB 1: REGISTRAR SOLICITUD
with tab1:
    st.header("Registrar Nueva Solicitud")
    
    if len(df_empleados) == 0:
        st.warning("⚠️ No hay empleados registrados")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            opciones = [(e['ID'], f"{e['PATERNO']} {e['MATERNO']} {e['NOMBRE']} - {e['PUESTO']} ({int(e['DIAS_REALES'])} días)") 
                        for _, e in df_empleados.iterrows()]
            emp_id = st.selectbox("Seleccionar Empleado", [o[0] for o in opciones], 
                                  format_func=lambda x: next(o[1] for o in opciones if o[0]==x))
            
            tipo = st.selectbox("Tipo de Permiso", list(NORMATIVA.keys()), 
                               format_func=lambda x: f"{NORMATIVA[x]['nombre']} (max. {NORMATIVA[x]['max_dias']} días)")
        
        with col2:
            dias = st.number_input("Número de Días", 1, NORMATIVA[tipo]['max_dias'], 1)
            aprobado = st.text_input("Aprobado Por", "Jefe de Departamento")
        
        st.markdown("---")
        st.subheader("📅 Fechas Solicitadas")
        
        # Selector de tipo de fechas
        tipo_fechas = st.radio(
            "¿Cómo quieres ingresar las fechas?",
            ["Consecutivas (rango)", "NO consecutivas (manual)"],
            horizontal=True
        )
        
        fechas_procesadas = []
        
        if tipo_fechas == "Consecutivas (rango)":
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                fecha_inicio_input = st.date_input("Fecha de Inicio", value=datetime.now())
            with col_f2:
                fecha_fin_input = st.date_input("Fecha de Fin", value=datetime.now() + timedelta(days=dias-1))
            
            # Generar todas las fechas del rango
            fecha_actual = fecha_inicio_input
            while fecha_actual <= fecha_fin_input:
                fechas_procesadas.append(datetime.combine(fecha_actual, datetime.min.time()))
                fecha_actual += timedelta(days=1)
            
            dias_rango = len(fechas_procesadas)
            if dias_rango == dias:
                st.success(f"✅ {dias_rango} fecha(s): {fecha_inicio_input.strftime('%d/%m/%Y')} al {fecha_fin_input.strftime('%d/%m/%Y')}")
            else:
                st.warning(f"⚠️ El rango tiene {dias_rango} días pero solicitaste {dias}")
        
        else:
            fechas_input = st.text_input(
                "Escribe las fechas separadas por comas (formato: dd/mm/yyyy)",
                placeholder="Ejemplo: 05/01/2025, 10/01/2025, 20/01/2025",
                help="Puedes solicitar días NO consecutivos"
            )
            
            if fechas_input:
                try:
                    for f in fechas_input.split(','):
                        fecha_obj = datetime.strptime(f.strip(), '%d/%m/%Y')
                        fechas_procesadas.append(fecha_obj)
                    fechas_procesadas.sort()
                    st.success(f"✅ {len(fechas_procesadas)} fecha(s) válida(s): {', '.join([f.strftime('%d/%m/%Y') for f in fechas_procesadas])}")
                    
                    if len(fechas_procesadas) != dias:
                        st.warning(f"⚠️ Solicitaste {dias} días pero ingresaste {len(fechas_procesadas)} fechas")
                except:
                    st.error("❌ Formato incorrecto. Usa: dd/mm/yyyy, dd/mm/yyyy")
        
        motivo = st.text_area("Motivo/Descripción", height=100)
        
        # Info empleado
        emp_info = df_empleados[df_empleados['ID']==emp_id].iloc[0]
        st.info(f"""
        **📋 Información del Empleado:**
        - **RFC:** {emp_info['RFC']}
        - **Puesto:** {emp_info['PUESTO']}
        - **Centro de Trabajo:** {emp_info.get('CENTRO DE TRABAJO', 'N/A')}
        - **Días Disponibles:** **{emp_info['DIAS_REALES']}/9**
        """)
        
        st.markdown("---")
        
        if st.button("✅ REGISTRAR SOLICITUD", type="primary", use_container_width=True):
            if not fechas_procesadas:
                st.error("❌ Debes ingresar al menos una fecha válida")
            elif len(fechas_procesadas) != dias:
                st.error(f"❌ El número de fechas ({len(fechas_procesadas)}) no coincide con los días solicitados ({dias})")
            else:
                fecha_inicio = fechas_procesadas[0]
                fecha_fin = fechas_procesadas[-1]
                
                errores, advertencias = validar_solicitud(emp_id, tipo, dias, fecha_inicio, df_empleados, df_solicitudes)
                
                if errores:
                    st.error("**❌ SOLICITUD RECHAZADA**")
                    for error in errores:
                        st.error(error)
                else:
                    for adv in advertencias:
                        st.warning(adv)
                    
                    nombre = f"{emp_info['PATERNO']} {emp_info['MATERNO']} {emp_info['NOMBRE']}"
                    fechas_str = ", ".join([f.strftime('%d/%m/%Y') for f in fechas_procesadas])
                    
                    nuevo_id = len(df_solicitudes) + 1
                    nueva_fila = [
                        nuevo_id, emp_id, emp_info['RFC'], nombre, tipo,
                        fecha_inicio.strftime('%Y-%m-%d'),
                        fecha_fin.strftime('%Y-%m-%d'),
                        dias,
                        f"{motivo} | Fechas: {fechas_str}",
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        aprobado,
                        st.session_state['nombre_usuario']
                    ]
                    
                    sheet_sol.append_row(nueva_fila)
                    dias_restantes = int(emp_info['DIAS_REALES'] - dias) if tipo == 'economico' else int(emp_info['DIAS_REALES'])
                    
                    # CONFIRMACIÓN
                    st.success("# ✅ ¡SOLICITUD REGISTRADA EXITOSAMENTE!")
                    st.balloons()
                    st.success(f"### 📋 Folio: {nuevo_id}")
                    st.success(f"### 👤 {nombre}")
                    st.success(f"### 📅 Fechas: {fechas_str}")
                    st.success(f"### 📊 Días restantes: **{dias_restantes}/9**")
                    st.success(f"### ✍️ Registrado por: {st.session_state['nombre_usuario']}")
                    st.toast(f"✅ Solicitud #{nuevo_id} registrada", icon="✅")
                    
                    if st.button("🔄 Registrar Otra Solicitud"):
                        st.rerun()

# TAB 2: VER EMPLEADOS
with tab2:
    st.header("👥 Plantilla de Personal")
    
    if len(df_empleados) > 0:
        col1, col2 = st.columns([2,1])
        with col1:
            busqueda = st.text_input("🔍 Buscar por nombre, RFC o puesto")
        with col2:
            if st.button("🔄 Actualizar Datos"):
                st.rerun()
        
        df_filtrado = df_empleados.copy()
        if busqueda:
            mascara = (
                df_filtrado['PATERNO'].str.contains(busqueda, case=False, na=False) |
                df_filtrado['MATERNO'].str.contains(busqueda, case=False, na=False) |
                df_filtrado['NOMBRE'].str.contains(busqueda, case=False, na=False) |
                df_filtrado['RFC'].str.contains(busqueda, case=False, na=False) |
                df_filtrado['PUESTO'].str.contains(busqueda, case=False, na=False)
            )
            df_filtrado = df_filtrado[mascara]
        
        st.info(f"📊 Mostrando {len(df_filtrado)} de {len(df_empleados)} empleados")
        
        # Seleccionar columnas a mostrar
        columnas_mostrar = ['RFC', 'PATERNO', 'MATERNO', 'NOMBRE', 'PUESTO', 'DIAS_REALES']
        df_mostrar = df_filtrado[columnas_mostrar].copy()
        df_mostrar = df_mostrar.rename(columns={'DIAS_REALES': 'DIAS DISPONIBLES'})
        
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay empleados registrados")

# TAB 3: ESTATUS INDIVIDUAL
with tab3:
    st.header("📊 Estatus Individual de Empleados")
    
    if len(df_empleados) > 0:
        busqueda = st.text_input("🔍 Buscar empleado", key="busq_individual")
        
        df_filtrado = df_empleados
        if busqueda:
            mascara = (
                df_filtrado['PATERNO'].str.contains(busqueda, case=False, na=False) |
                df_filtrado['MATERNO'].str.contains(busqueda, case=False, na=False) |
                df_filtrado['NOMBRE'].str.contains(busqueda, case=False, na=False) |
                df_filtrado['RFC'].str.contains(busqueda, case=False, na=False)
            )
            df_filtrado = df_filtrado[mascara]
        
        for _, emp in df_filtrado.iterrows():
            nombre = f"{emp['PATERNO']} {emp['MATERNO']} {emp['NOMBRE']}"
            
            with st.expander(f"👤 {nombre} - {emp['PUESTO']}"):
                col1, col2, col3, col4 = st.columns(4)
                
                dias_disp = int(emp['DIAS_REALES'])
                color = "🟢" if dias_disp > 3 else "🟡" if dias_disp > 1 else "🔴"
                
                with col1:
                    st.metric("Días Disponibles", f"{color} {dias_disp}/9")
                with col2:
                    solicitudes_emp = df_solicitudes[df_solicitudes['EmpleadoID'] == emp['ID']]
                    st.metric("Total Solicitudes", len(solicitudes_emp))
                with col3:
                    st.metric("RFC", emp['RFC'])
                with col4:
                    st.metric("Tipo", emp.get('BASE/INTERINO', 'N/A'))
                
                st.markdown("**Información Completa:**")
                info_cols = st.columns(2)
                with info_cols[0]:
                    st.write(f"**CURP:** {emp.get('CURP', 'N/A')}")
                    st.write(f"**Plaza:** {emp.get('PLAZA', 'N/A')}")
                with info_cols[1]:
                    st.write(f"**Centro:** {emp.get('CENTRO DE TRABAJO', 'N/A')}")
                    st.write(f"**Quincena:** {emp.get('QNA FIN', 'N/A')}")
                
                if len(solicitudes_emp) > 0:
                    st.markdown("---")
                    st.markdown("**📋 Historial de Solicitudes:**")
                    columnas = ['Tipo Permiso', 'Fecha Inicio', 'Fecha Fin', 'Dias Solicitados', 'Motivo', 'Aprobado Por']
                    if 'Registrado Por' in solicitudes_emp.columns:
                        columnas.append('Registrado Por')
                    st.dataframe(solicitudes_emp[columnas], use_container_width=True, hide_index=True)

# TAB 4: REPORTES
with tab4:
    st.header("📄 Generación de Reportes")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 Reportes de Empleados")
        if st.button("Descargar Plantilla (Excel)", use_container_width=True):
            if len(df_empleados) > 0:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_empleados.to_excel(writer, sheet_name='Empleados', index=False)
                
                st.download_button(
                    "💾 Descargar Excel",
                    output.getvalue(),
                    f"empleados_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    with col2:
        st.subheader("📥 Reportes de Solicitudes")
        if st.button("Descargar Historial (Excel)", use_container_width=True):
            if len(df_solicitudes) > 0:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_solicitudes.to_excel(writer, sheet_name='Solicitudes', index=False)
                
                st.download_button(
                    "💾 Descargar Excel",
                    output.getvalue(),
                    f"solicitudes_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    if len(df_empleados) > 0:
        st.markdown("---")
        st.subheader("📊 Estadísticas Generales")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Empleados", len(df_empleados))
        with col2:
            criticos = len(df_empleados[df_empleados['DIAS_REALES'] <= 1])
            st.metric("⚠️ Críticos", criticos)
        with col3:
            total_dias = df_empleados['DIAS_REALES'].sum()
            st.metric("Total Días Disponibles", int(total_dias))
        with col4:
            if len(df_solicitudes) > 0:
                df_solicitudes['Fecha_Reg'] = pd.to_datetime(df_solicitudes['Fecha Registro'], errors='coerce')
                dias_usados = df_solicitudes[df_solicitudes['Fecha_Reg'].dt.year == datetime.now().year]['Dias Solicitados'].sum()
                st.metric("Días Usados (2025)", int(dias_usados))

# TAB 5: NORMATIVA
with tab5:
    st.header("📋 Normativa Aplicable")
    
    st.info("""
    **Reglamento de las Condiciones Generales de Trabajo**  
    Secretaría de Educación del Estado de Jalisco
    """)
    
    st.markdown("### Días Económicos (Asuntos Particulares)")
    st.markdown("""
    - ✅ Hasta **3 días hábiles** por ocasión
    - ✅ Máximo **3 ocasiones** por año calendario
    - ✅ Intervalo mínimo de **30 días** (desde el último día usado hasta el inicio del siguiente)
    - ✅ Otorgados por el Jefe de Dependencia
    """)
    
    st.markdown("---")
    st.markdown("### Otras Licencias con Goce de Sueldo")
    
    tabla = pd.DataFrame([
        {
            'Motivo': v['nombre'], 
            'Duración': f"{v['max_dias']} día(s)", 
            'Límite': v['limite'],
            'Condiciones': v['descripcion']
        }
        for v in NORMATIVA.values()
    ])
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.warning("""
    **⚠️ IMPORTANTE - Límites de Uso:**
    
    - **Matrimonio**: Solo 1 vez EN LA VIDA
    - **Jubilación**: Solo 1 vez EN LA VIDA (cuando se jubila)
    - **Examen Profesional**: Máximo 3 veces (licenciatura, maestría, doctorado)
    - **Mudanza**: Máximo 2 veces por año
    - **Fallecimiento**: Sin límite (puede ocurrir varias veces)
    - **Días Económicos**: 3 ocasiones por año calendario
    """)