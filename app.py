import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import io

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================

st.set_page_config(
    page_title="Sistema Días Económicos",
    page_icon="📅",
    layout="wide"
)

# Configuración de Google Sheets
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def conectar_sheets():
    """Conecta con Google Sheets usando credenciales"""
    try:
        credentials_dict = st.secrets["google_sheets"]
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPES
        )
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")
        return None

# Normativa oficial
NORMATIVA = {
    'economico': {
        'nombre': 'Día Económico',
        'max_dias': 3,
        'max_ocasiones': 3,
        'intervalo_dias': 30,
        'descripcion': 'Asuntos particulares'
    },
    'matrimonio': {
        'nombre': 'Matrimonio',
        'max_dias': 10,
        'max_ocasiones': 1,
        'descripcion': 'Por una sola ocasión'
    },
    'fallecimiento': {
        'nombre': 'Fallecimiento/Enfermedad Grave',
        'max_dias': 5,
        'descripcion': 'Parientes primer grado'
    },
    'jubilacion': {
        'nombre': 'Trámites Jubilación',
        'max_dias': 2,
        'descripcion': 'Gestiones de jubilación'
    },
    'examen': {
        'nombre': 'Examen Profesional/Tesis',
        'max_dias': 3,
        'descripcion': 'Presentación de grado'
    },
    'mudanza': {
        'nombre': 'Cambio de Domicilio',
        'max_dias': 1,
        'descripcion': 'Para mudanza'
    }
}

# ============================================
# FUNCIONES DE GOOGLE SHEETS
# ============================================

@st.cache_resource
def get_sheets_client():
    """Obtiene el cliente de Google Sheets (cacheado)"""
    return conectar_sheets()

def inicializar_sheets(client):
    """Crea las hojas necesarias si no existen"""
    try:
        SPREADSHEET_NAME = "Dias_Economicos_Formacion_Continua"
        
        try:
            spreadsheet = client.open(SPREADSHEET_NAME)
        except gspread.SpreadsheetNotFound:
            spreadsheet = client.create(SPREADSHEET_NAME)
            st.success(f"Archivo '{SPREADSHEET_NAME}' creado exitosamente")
        
        # Verificar/crear hoja de Empleados con TODOS los campos
        try:
            sheet_empleados = spreadsheet.worksheet("Empleados")
        except gspread.WorksheetNotFound:
            sheet_empleados = spreadsheet.add_worksheet(
                title="Empleados", 
                rows=500, 
                cols=15
            )
            # Encabezados completos según tu plantilla
            sheet_empleados.update('A1:M1', [[
                'ID', 'RFC', 'CURP', 'PATERNO', 'MATERNO', 'NOMBRE',
                'PLAZA', 'PUESTO', 'BASE/INTERINO', 'QNA FIN', 
                'C.C.T.', 'CENTRO DE TRABAJO', 'DIAS DISPONIBLES'
            ]])
        
        # Verificar/crear hoja de Solicitudes
        try:
            sheet_solicitudes = spreadsheet.worksheet("Solicitudes")
        except gspread.WorksheetNotFound:
            sheet_solicitudes = spreadsheet.add_worksheet(
                title="Solicitudes",
                rows=2000,
                cols=15
            )
            sheet_solicitudes.update('A1:K1', [[
                'ID', 'EmpleadoID', 'RFC', 'Nombre Completo', 'Tipo Permiso', 
                'Fecha Inicio', 'Fecha Fin', 'Dias Solicitados', 
                'Motivo', 'Fecha Registro', 'Aprobado Por'
            ]])
        
        return spreadsheet, sheet_empleados, sheet_solicitudes
    
    except Exception as e:
        st.error(f"Error inicializando sheets: {e}")
        return None, None, None

def cargar_empleados(sheet):
    """Carga datos de empleados desde Google Sheets"""
    try:
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=[
                'ID', 'RFC', 'CURP', 'PATERNO', 'MATERNO', 'NOMBRE',
                'PLAZA', 'PUESTO', 'BASE/INTERINO', 'QNA FIN', 
                'C.C.T.', 'CENTRO DE TRABAJO', 'DIAS DISPONIBLES'
            ])
        df = pd.DataFrame(data)
        # Crear columna de nombre completo para facilitar búsquedas
        if 'PATERNO' in df.columns and 'MATERNO' in df.columns and 'NOMBRE' in df.columns:
            df['NOMBRE_COMPLETO'] = df['PATERNO'] + ' ' + df['MATERNO'] + ' ' + df['NOMBRE']
        return df
    except Exception as e:
        st.error(f"Error cargando empleados: {e}")
        return pd.DataFrame()

def cargar_solicitudes(sheet):
    """Carga datos de solicitudes desde Google Sheets"""
    try:
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=[
                'ID', 'EmpleadoID', 'RFC', 'Nombre Completo', 'Tipo Permiso',
                'Fecha Inicio', 'Fecha Fin', 'Dias Solicitados',
                'Motivo', 'Fecha Registro', 'Aprobado Por'
            ])
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error cargando solicitudes: {e}")
        return pd.DataFrame()

def guardar_solicitud(sheet, solicitud):
    """Guarda una nueva solicitud en Google Sheets"""
    try:
        nueva_fila = [
            solicitud['ID'],
            solicitud['EmpleadoID'],
            solicitud['RFC'],
            solicitud['Nombre Completo'],
            solicitud['Tipo Permiso'],
            solicitud['Fecha Inicio'],
            solicitud['Fecha Fin'],
            solicitud['Dias Solicitados'],
            solicitud['Motivo'],
            solicitud['Fecha Registro'],
            solicitud['Aprobado Por']
        ]
        sheet.append_row(nueva_fila)
        return True
    except Exception as e:
        st.error(f"Error guardando solicitud: {e}")
        return False

def actualizar_dias_empleado(sheet, empleado_id, nuevos_dias):
    """Actualiza los días disponibles de un empleado"""
    try:
        cell = sheet.find(str(empleado_id))
        fila = cell.row
        # Columna M (DIAS DISPONIBLES) es la columna 13
        sheet.update_cell(fila, 13, nuevos_dias)
        return True
    except Exception as e:
        st.error(f"Error actualizando días: {e}")
        return False

def importar_empleados_desde_excel(sheet, df_excel):
    """Importa empleados desde el Excel de plantilla"""
    try:
        # Limpiar datos existentes (excepto encabezados)
        sheet.delete_rows(2, sheet.row_count)
        
        contador = 0
        for idx, row in df_excel.iterrows():
            # Asignar ID automático
            empleado_id = idx + 1
            
            # Preparar fila con todos los campos
            nueva_fila = [
                empleado_id,
                str(row.get('RFC', '')).strip(),
                str(row.get('CURP', '')).strip(),
                str(row.get('PATERNO', '')).strip(),
                str(row.get('MATERNO', '')).strip(),
                str(row.get('NOMBRE', '')).strip(),
                str(row.get('PLAZA', '')).strip(),
                str(row.get('PUESTO', '')).strip(),
                str(row.get('BASE/INTERINO', '')).strip(),
                str(row.get('QNA FIN', '')).strip(),
                str(row.get('C. C. T.', '')).strip() or str(row.get('C.C.T.', '')).strip(),
                str(row.get('CENTRO DE TRABAJO', '')).strip(),
                9  # Días disponibles iniciales
            ]
            
            sheet.append_row(nueva_fila)
            contador += 1
        
        return contador
    except Exception as e:
        st.error(f"Error importando empleados: {e}")
        return 0

# ============================================
# VALIDACIONES
# ============================================

def validar_solicitud(empleado_id, tipo_permiso, dias_solicitados, df_empleados, df_solicitudes):
    """Valida una solicitud según la normativa"""
    errores = []
    advertencias = []
    
    # Obtener datos del empleado
    empleado = df_empleados[df_empleados['ID'] == empleado_id].iloc[0]
    dias_disponibles = int(empleado['DIAS DISPONIBLES'])
    
    # Configuración del tipo de permiso
    config = NORMATIVA[tipo_permiso]
    
    # Validación 1: Días máximos permitidos
    if dias_solicitados > config['max_dias']:
        errores.append(f"❌ Máximo permitido: {config['max_dias']} días para {config['nombre']}")
    
    # Validaciones específicas para días económicos
    if tipo_permiso == 'economico':
        # Filtrar solicitudes económicas del año actual
        año_actual = datetime.now().year
        solicitudes_economicas = df_solicitudes[
            (df_solicitudes['EmpleadoID'] == empleado_id) &
            (df_solicitudes['Tipo Permiso'] == 'economico') &
            (pd.to_datetime(df_solicitudes['Fecha Registro']).dt.year == año_actual)
        ]
        
        # Validación 2: Número de ocasiones en el año
        if len(solicitudes_economicas) >= config['max_ocasiones']:
            errores.append(f"❌ Ya alcanzó el límite de {config['max_ocasiones']} ocasiones en el año")
        
        # Validación 3: Intervalo entre solicitudes
        if len(solicitudes_economicas) > 0:
            ultima_fecha = pd.to_datetime(solicitudes_economicas['Fecha Registro'].iloc[-1])
            dias_desde_ultima = (datetime.now() - ultima_fecha).days
            
            if dias_desde_ultima < config['intervalo_dias']:
                dias_faltantes = config['intervalo_dias'] - dias_desde_ultima
                errores.append(
                    f"❌ Debe esperar {dias_faltantes} días más "
                    f"(intervalo mínimo: {config['intervalo_dias']} días)"
                )
        
        # Validación 4: Días disponibles
        if dias_solicitados > dias_disponibles:
            errores.append(
                f"❌ Solo tiene {dias_disponibles} días disponibles "
                f"(solicitó {dias_solicitados})"
            )
        
        # Advertencia si quedan pocos días
        if dias_disponibles - dias_solicitados <= 2:
            advertencias.append(
                f"⚠️ Después de esta solicitud quedarán "
                f"{dias_disponibles - dias_solicitados} días disponibles"
            )
    
    # Validación especial: Matrimonio (solo una vez)
    if tipo_permiso == 'matrimonio':
        solicitudes_matrimonio = df_solicitudes[
            (df_solicitudes['EmpleadoID'] == empleado_id) &
            (df_solicitudes['Tipo Permiso'] == 'matrimonio')
        ]
        if len(solicitudes_matrimonio) > 0:
            errores.append("❌ La licencia por matrimonio solo se otorga una vez")
    
    return errores, advertencias

# ============================================
# ALERTAS Y NOTIFICACIONES
# ============================================

def generar_alertas(df_empleados):
    """Genera alertas para empleados con pocos días disponibles"""
    alertas = []
    
    for _, emp in df_empleados.iterrows():
        dias = int(emp['DIAS DISPONIBLES'])
        nombre_completo = f"{emp['PATERNO']} {emp['MATERNO']} {emp['NOMBRE']}"
        
        if dias == 0:
            alertas.append({
                'tipo': 'error',
                'empleado': nombre_completo,
                'mensaje': f"🚫 {nombre_completo} NO tiene días económicos disponibles"
            })
        elif dias == 1:
            alertas.append({
                'tipo': 'warning',
                'empleado': nombre_completo,
                'mensaje': f"⚠️ {nombre_completo} tiene solo 1 día económico disponible"
            })
        elif dias <= 3:
            alertas.append({
                'tipo': 'info',
                'empleado': nombre_completo,
                'mensaje': f"ℹ️ {nombre_completo} tiene {dias} días económicos disponibles"
            })
    
    return alertas

# ============================================
# INTERFAZ PRINCIPAL
# ============================================

def main():
    st.title("📅 Sistema de Gestión de Días Económicos")
    st.markdown("**Dirección de Formación Continua** - Secretaría de Educación Jalisco")
    st.markdown("---")
    
    # Conectar a Google Sheets
    client = get_sheets_client()
    
    if client is None:
        st.error("⚠️ No se pudo conectar a Google Sheets. Verifica las credenciales.")
        st.info("""
        **Instrucciones de configuración:**
        1. Ve a Settings > Secrets en tu app de Streamlit
        2. Agrega tus credenciales de Google Service Account
        """)
        return
    
    # Inicializar sheets
    spreadsheet, sheet_empleados, sheet_solicitudes = inicializar_sheets(client)
    
    if spreadsheet is None:
        st.error("No se pudieron inicializar las hojas de cálculo")
        return
    
    # Cargar datos
    df_empleados = cargar_empleados(sheet_empleados)
    df_solicitudes = cargar_solicitudes(sheet_solicitudes)
    
    # Sidebar: Alertas
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
            
            # Estadísticas adicionales
            dias_promedio = df_empleados['DIAS DISPONIBLES'].mean()
            st.metric("Días Disponibles (Promedio)", f"{dias_promedio:.1f}")
    
    # Tabs principales
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📝 Registrar Solicitud",
        "📥 Importar Plantilla",
        "👥 Ver Empleados",
        "📊 Estatus Individual",
        "📄 Reportes",
        "📋 Normativa"
    ])
    
    # TAB 1: REGISTRAR SOLICITUD
    with tab1:
        st.header("Registrar Nueva Solicitud")
        
        if len(df_empleados) == 0:
            st.warning("⚠️ Primero debes importar la plantilla de personal en la pestaña 'Importar Plantilla'")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                # Crear lista de opciones con nombre completo
                opciones_empleados = df_empleados.apply(
                    lambda x: (x['ID'], f"{x['PATERNO']} {x['MATERNO']} {x['NOMBRE']} - {x['PUESTO']} ({x['DIAS DISPONIBLES']} días)"),
                    axis=1
                ).tolist()
                
                empleado_seleccionado = st.selectbox(
                    "Seleccionar Empleado",
                    options=[opt[0] for opt in opciones_empleados],
                    format_func=lambda x: next(opt[1] for opt in opciones_empleados if opt[0] == x)
                )
                
                tipo_permiso = st.selectbox(
                    "Tipo de Permiso",
                    options=list(NORMATIVA.keys()),
                    format_func=lambda x: f"{NORMATIVA[x]['nombre']} (max. {NORMATIVA[x]['max_dias']} días)"
                )
                
                fecha_inicio = st.date_input("Fecha de Inicio", value=datetime.now())
            
            with col2:
                dias_solicitados = st.number_input(
                    "Número de Días",
                    min_value=1,
                    max_value=NORMATIVA[tipo_permiso]['max_dias'],
                    value=1
                )
                
                fecha_fin = st.date_input(
                    "Fecha de Fin",
                    value=fecha_inicio + timedelta(days=dias_solicitados-1)
                )
                
                aprobado_por = st.text_input("Aprobado Por", value="Jefe de Departamento")
            
            motivo = st.text_area("Motivo/Descripción", height=100)
            
            # Mostrar información del empleado seleccionado
            if empleado_seleccionado:
                emp_info = df_empleados[df_empleados['ID'] == empleado_seleccionado].iloc[0]
                st.info(f"""
                **Información del Empleado:**
                - **RFC:** {emp_info['RFC']}
                - **Puesto:** {emp_info['PUESTO']}
                - **Centro de Trabajo:** {emp_info['CENTRO DE TRABAJO']}
                - **Días Disponibles:** {emp_info['DIAS DISPONIBLES']}/9
                """)
            
            st.markdown("---")
            
            if st.button("✅ Validar y Registrar Solicitud", type="primary", use_container_width=True):
                # Validar
                errores, advertencias = validar_solicitud(
                    empleado_seleccionado,
                    tipo_permiso,
                    dias_solicitados,
                    df_empleados,
                    df_solicitudes
                )
                
                # Mostrar advertencias
                for adv in advertencias:
                    st.warning(adv)
                
                # Si hay errores, no permitir el registro
                if errores:
                    st.error("**❌ SOLICITUD RECHAZADA**")
                    for error in errores:
                        st.error(error)
                else:
                    # Crear solicitud
                    empleado = df_empleados[df_empleados['ID']==empleado_seleccionado].iloc[0]
                    nombre_completo = f"{empleado['PATERNO']} {empleado['MATERNO']} {empleado['NOMBRE']}"
                    
                    nueva_solicitud = {
                        'ID': len(df_solicitudes) + 1,
                        'EmpleadoID': empleado_seleccionado,
                        'RFC': empleado['RFC'],
                        'Nombre Completo': nombre_completo,
                        'Tipo Permiso': tipo_permiso,
                        'Fecha Inicio': fecha_inicio.strftime('%Y-%m-%d'),
                        'Fecha Fin': fecha_fin.strftime('%Y-%m-%d'),
                        'Dias Solicitados': dias_solicitados,
                        'Motivo': motivo,
                        'Fecha Registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'Aprobado Por': aprobado_por
                    }
                    
                    # Guardar en Sheets
                    if guardar_solicitud(sheet_solicitudes, nueva_solicitud):
                        # Actualizar días disponibles si es día económico
                        if tipo_permiso == 'economico':
                            nuevos_dias = int(empleado['DIAS DISPONIBLES']) - dias_solicitados
                            actualizar_dias_empleado(sheet_empleados, empleado_seleccionado, nuevos_dias)
                        
                        st.success("✅ **Solicitud registrada exitosamente**")
                        st.balloons()
                        st.rerun()
    
    # TAB 2: IMPORTAR PLANTILLA
    with tab2:
        st.header("📥 Importar Plantilla de Personal")
        
        st.info("""
        **Formato esperado del Excel:**
        
        El archivo debe contener las siguientes columnas:
        - RFC
        - CURP
        - PATERNO
        - MATERNO
        - NOMBRE
        - PLAZA
        - PUESTO
        - BASE/INTERINO
        - QNA FIN
        - C. C. T. (o C.C.T.)
        - CENTRO DE TRABAJO
        """)
        
        archivo_excel = st.file_uploader(
            "Selecciona el archivo Excel con la plantilla de personal",
            type=['xlsx', 'xls'],
            help="Sube tu archivo Excel con la plantilla completa"
        )
        
        if archivo_excel is not None:
            try:
                # Leer el archivo Excel
                df_excel = pd.read_excel(archivo_excel)
                
                st.success(f"✅ Archivo cargado: {len(df_excel)} registros encontrados")
                
                # Mostrar vista previa
                st.subheader("Vista Previa de Datos")
                st.dataframe(df_excel.head(10), use_container_width=True)
                
                # Verificar columnas requeridas
                columnas_requeridas = ['RFC', 'PATERNO', 'MATERNO', 'NOMBRE', 'PUESTO']
                columnas_faltantes = [col for col in columnas_requeridas if col not in df_excel.columns]
                
                if columnas_faltantes:
                    st.error(f"⚠️ Columnas faltantes: {', '.join(columnas_faltantes)}")
                else:
                    st.success("✅ Todas las columnas requeridas están presentes")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Total de Empleados", len(df_excel))
                    
                    with col2:
                        if 'PUESTO' in df_excel.columns:
                            puestos_unicos = df_excel['PUESTO'].nunique()
                            st.metric("Puestos Diferentes", puestos_unicos)
                    
                    st.markdown("---")
                    
                    # Confirmar importación
                    st.warning("⚠️ **IMPORTANTE**: Esta acción reemplazará todos los empleados existentes en el sistema.")
                    
                    confirmar = st.checkbox("Confirmo que deseo importar estos datos")
                    
                    if confirmar:
                        if st.button("🚀 Importar Empleados a Google Sheets", type="primary", use_container_width=True):
                            with st.spinner("Importando empleados..."):
                                empleados_importados = importar_empleados_desde_excel(sheet_empleados, df_excel)
                                
                                if empleados_importados > 0:
                                    st.success(f"✅ **¡Importación exitosa!**")
                                    st.success(f"Se importaron {empleados_importados} empleados correctamente")
                                    st.balloons()
                                    
                                    # Recargar datos
                                    st.rerun()
                                else:
                                    st.error("❌ Error durante la importación")
            
            except Exception as e:
                st.error(f"❌ Error al leer el archivo: {e}")
                st.info("Verifica que el archivo sea un Excel válido (.xlsx o .xls)")
    
    # TAB 3: VER EMPLEADOS
    with tab3:
        st.header("👥 Plantilla de Personal")
        
        if len(df_empleados) > 0:
            # Búsqueda y filtros
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                busqueda = st.text_input("🔍 Buscar por nombre, RFC o puesto", "")
            
            with col2:
                if 'PUESTO' in df_empleados.columns:
                    puestos = ['Todos'] + sorted(df_empleados['PUESTO'].unique().tolist())
                    puesto_filtro = st.selectbox("Filtrar por Puesto", puestos)
            
            with col3:
                if 'BASE/INTERINO' in df_empleados.columns:
                    tipos = ['Todos'] + sorted(df_empleados['BASE/INTERINO'].unique().tolist())
                    tipo_filtro = st.selectbox("Filtrar por Tipo", tipos)
            
            # Aplicar filtros
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
            
            if puesto_filtro != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['PUESTO'] == puesto_filtro]
            
            if tipo_filtro != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['BASE/INTERINO'] == tipo_filtro]
            
            st.info(f"📊 Mostrando {len(df_filtrado)} de {len(df_empleados)} empleados")
            
            # Mostrar tabla
            st.dataframe(
                df_filtrado,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "DIAS DISPONIBLES": st.column_config.ProgressColumn(
                        "Días Disponibles",
                        help="Días económicos disponibles",
                        format="%d/9",
                        min_value=0,
                        max_value=9,
                    ),
                }
            )
        else:
            st.warning("📭 No hay empleados registrados. Importa la plantilla de personal.")
    
    # TAB 4: ESTATUS INDIVIDUAL
    with tab4:
        st.header("📊 Estatus Individual de Empleados")
        
        if len(df_empleados) > 0:
            busqueda = st.text_input("🔍 Buscar empleado", "")
            
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
                nombre_completo = f"{emp['PATERNO']} {emp['MATERNO']} {emp['NOMBRE']}"
                
                with st.expander(f"👤 {nombre_completo} - {emp['PUESTO']}"):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    dias_disp = int(emp['DIAS DISPONIBLES'])
                    
                    with col1:
                        color = "🟢" if dias_disp > 3 else "🟡" if dias_disp > 1 else "🔴"
                        st.metric("Días Disponibles", f"{color} {dias_disp}/9")
                    
                    with col2:
                        solicitudes_emp = df_solicitudes[df_solicitudes['EmpleadoID'] == emp['ID']]
                        st.metric("Total Solicitudes", len(solicitudes_emp))
                    
                    with col3:
                        st.metric("RFC", emp['RFC'])
                    
                    with col4:
                        st.metric("Tipo", emp.get('BASE/INTERINO', 'N/A'))
                    
                    # Información completa
                    st.markdown("**Información Completa:**")
                    info_cols = st.columns(2)
                    with info_cols[0]:
                        st.write(f"**CURP:** {emp.get('CURP', 'N/A')}")
                        st.write(f"**Plaza:** {emp.get('PLAZA', 'N/A')}")
                        st.write(f"**C.C.T.:** {emp.get('C.C.T.', emp.get('C. C. T.', 'N/A'))}")
                    with info_cols[1]:
                        st.write(f"**Centro de Trabajo:** {emp.get('CENTRO DE TRABAJO', 'N/A')}")
                        st.write(f"**Quincena Fin:** {emp.get('QNA FIN', 'N/A')}")
                    
                    # Historial de solicitudes
                    if len(solicitudes_emp) > 0:
                        st.markdown("---")
                        st.markdown("**📋 Historial de Solicitudes:**")
                        st.dataframe(
                            solicitudes_emp[['Tipo Permiso', 'Fecha Inicio', 'Fecha Fin', 'Dias Solicitados', 'Motivo', 'Aprobado Por']],
                            use_container_width=True,
                            hide_index=True
                        )
        else:
            st.info("No hay empleados registrados")
    
    # TAB 5: REPORTES
    with tab5:
        st.header("📄 Generación de Reportes")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📥 Reportes de Empleados")
            
            if st.button("Descargar Plantilla Completa (Excel)", use_container_width=True):
                if len(df_empleados) > 0:
                    # Crear Excel en memoria
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_empleados.to_excel(writer, sheet_name='Empleados', index=False)
                    
                    st.download_button(
                        "💾 Descargar Excel",
                        output.getvalue(),
                        f"plantilla_empleados_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("No hay datos para descargar")
            
            if st.button("Descargar Reporte de Días Disponibles (CSV)", use_container_width=True):
                if len(df_empleados) > 0:
                    reporte = df_empleados[['RFC', 'PATERNO', 'MATERNO', 'NOMBRE', 'PUESTO', 'DIAS DISPONIBLES']].copy()
                    reporte['NOMBRE_COMPLETO'] = reporte['PATERNO'] + ' ' + reporte['MATERNO'] + ' ' + reporte['NOMBRE']
                    
                    csv = reporte.to_csv(index=False)
                    st.download_button(
                        "💾 Descargar CSV",
                        csv,
                        f"reporte_dias_disponibles_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv"
                    )
        
        with col2:
            st.subheader("📥 Reportes de Solicitudes")
            
            if st.button("Descargar Historial Completo (Excel)", use_container_width=True):
                if len(df_solicitudes) > 0:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_solicitudes.to_excel(writer, sheet_name='Solicitudes', index=False)
                    
                    st.download_button(
                        "💾 Descargar Excel",
                        output.getvalue(),
                        f"historial_solicitudes_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("No hay solicitudes registradas")
            
            if st.button("Descargar Reporte por Empleado (CSV)", use_container_width=True):
                if len(df_solicitudes) > 0:
                    csv = df_solicitudes.to_csv(index=False)
                    st.download_button(
                        "💾 Descargar CSV",
                        csv,
                        f"solicitudes_por_empleado_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv"
                    )
        
        # Estadísticas generales
        if len(df_empleados) > 0:
            st.markdown("---")
            st.subheader("📊 Estadísticas Generales")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_empleados = len(df_empleados)
                st.metric("Total Empleados", total_empleados)
            
            with col2:
                empleados_criticos = len(df_empleados[df_empleados['DIAS DISPONIBLES'] <= 1])
                st.metric("⚠️ Críticos (≤1 día)", empleados_criticos)
            
            with col3:
                dias_totales_disponibles = df_empleados['DIAS DISPONIBLES'].sum()
                st.metric("Total Días Disponibles", dias_totales_disponibles)
            
            with col4:
                if len(df_solicitudes) > 0:
                    dias_usados_año = df_solicitudes[
                        pd.to_datetime(df_solicitudes['Fecha Registro']).dt.year == datetime.now().year
                    ]['Dias Solicitados'].sum()
                    st.metric("Días Usados (Este Año)", int(dias_usados_año))
    
    # TAB 6: NORMATIVA
    with tab6:
        st.header("📋 Normativa Aplicable")
        
        st.info("""
        **Reglamento de las Condiciones Generales de Trabajo**  
        Secretaría de Educación del Estado de Jalisco
        """)
        
        st.markdown("### Días Económicos (Asuntos Particulares)")
        st.markdown("""
        - ✅ Hasta **3 días hábiles** por ocasión
        - ✅ Máximo **3 ocasiones** por año calendario
        - ✅ Intervalo mínimo de **1 mes** entre solicitudes
        - ✅ Otorgados por el Jefe de Dependencia
        """)
        
        st.markdown("---")
        st.markdown("### Otras Licencias con Goce de Sueldo")
        
        tabla_normativa = pd.DataFrame([
            {
                'Motivo': v['nombre'],
                'Duración': f"{v['max_dias']} día(s) hábil(es)",
                'Condiciones': v['descripcion']
            }
            for k, v in NORMATIVA.items()
        ])
        
        st.dataframe(tabla_normativa, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()