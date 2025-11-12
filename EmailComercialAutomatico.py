import streamlit as st
import pandas as pd
from pathlib import Path
from email.message import EmailMessage
import smtplib # Biblioteca para envio de e-mail

# --- Configurações da Página Streamlit ---
st.set_page_config(page_title="Análise de Relatórios Comerciais", page_icon="📊", layout="wide")
st.title("📊 Painel de Análise de Relatórios")

# --- Constantes e Configurações ---
FILE_PATH = r"C:\Users\mdornelas\OneDrive - AGP GROUP\Documentos\01. AÇÕES\Metas\IA\Agente de pedidos comercial\Cópia de PAINEL DE CONTROLE_EXPORTAÇÃO_NEW.xlsm"
SHEET_RELATORIO = 'RELATÓRIO'
SHEET_DADOS_APONT = 'DADOS_APONT'

FILTROS_PAIS = {
    'Todos': [], 'CAM': ['ÁFRICA DO SUL', 'DEFENSE', 'CENTROÁMERICA'],
    'MERCOSUL': ['MERCOSUL'], 'MÉXICO': ['MÉXICO']
}

# --- CREDENCIAIS DE E-MAIL (INSERIDAS DIRETAMENTE) ---
# ATENÇÃO: Prática insegura para código compartilhado. Use uma "Senha de Aplicativo" se o MFA estiver ativo.
SENDER_EMAIL = "mdornelas@agpglass.com"
SENDER_PASSWORD = "hflsrgjwtqsvwbzm"


# --- Funções de Carregamento de Dados ---
@st.cache_data
def load_data(file_path, sheet_name):
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
        if sheet_name == 'RELATÓRIO':
            colunas_de_data = ['FECHA GENESIS', 'PREVISTO PCP']
            for col in colunas_de_data:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%d/%m/%Y')
        return df
    except Exception as e:
        st.error(f"Ocorreu um erro ao ler a planilha '{sheet_name}': {e}")
        return None

# --- FUNÇÃO DE CRIAÇÃO E ENVIO DE E-MAIL VIA SMTP ---
def send_email_via_smtp(main_df: pd.DataFrame, details_df: pd.DataFrame | None, recipient: str, subject: str) -> bool:
    # As credenciais agora vêm das constantes definidas no topo do arquivo.
    sender_email = SENDER_EMAIL
    sender_password = SENDER_PASSWORD

    html_style = """
    <style>
        body { font-family: Calibri, sans-serif; font-size: 11pt; }
        table { border-collapse: collapse; width: 100%; font-size: 10pt; }
        th, td { border: 1px solid #A6A6A6; text-align: left; padding: 8px; }
        th { background-color: #E7E7E7; font-weight: bold; }
        h3 { font-family: Calibri, sans-serif; }
    </style>
    """
    html_table_main = main_df.to_html(index=False, escape=False, border=0)
    details_html_section = ""
    if details_df is not None and not details_df.empty:
        html_table_details = details_df.to_html(index=False, escape=False, border=0)
        details_html_section = f"""<br><hr><br><h3>Detalhes do Pedido</h3>{html_table_details}"""

    html_body = f"""
    <html><head>{html_style}</head><body>
        <p>Buen día,</p><p>Sigue o status solicitado.</p><br>
        <h3>Relatório Principal</h3>{html_table_main}{details_html_section}<br>
        <p>Atenciosamente,<br>Agente Inteligente PCP - AGP</p>
    </body></html>
    """
    
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP('smtp.office365.com', 587) as smtp:
            smtp.starttls()
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        return True
    except smtplib.SMTPAuthenticationError:
        st.error("ERRO DE AUTENTICAÇÃO: O e-mail ou a senha inseridos no código estão incorretos. Lembre-se de usar uma 'Senha de Aplicativo' se o MFA estiver ativo.")
        return False
    except Exception as e:
        st.error(f"ERRO ao enviar e-mail: {e}")
        return False

# --- Lógica da Interface ---

if st.button("🔍 Analisar Relatório"):
    with st.spinner("Carregando dados das planilhas..."):
        st.session_state.df_relatorio = load_data(FILE_PATH, SHEET_RELATORIO)
        st.session_state.df_dados_apont = load_data(FILE_PATH, SHEET_DADOS_APONT)

if 'df_relatorio' in st.session_state and st.session_state.df_relatorio is not None:
    st.divider()
    st.subheader("Filtro de Relatório")
    filtro_selecionado = st.selectbox("Filtrar por Região:", options=list(FILTROS_PAIS.keys()))
    paises_para_filtrar = FILTROS_PAIS[filtro_selecionado]
    
    df_filtrado_relatorio = st.session_state.df_relatorio[st.session_state.df_relatorio['PAÍS'].isin(paises_para_filtrar)].iloc[:, :13] if paises_para_filtrar else st.session_state.df_relatorio.iloc[:, :13]
    st.subheader(f"Relatório Principal - {filtro_selecionado}")
    st.dataframe(df_filtrado_relatorio, hide_index=True)
    
    st.divider()
    st.subheader("Consultar Pedido Específico")
    pedido_para_buscar = st.text_input("Abrir Pedido (informe o número ORDEN SAP):")

    df_detalhes_pedido = None
    if pedido_para_buscar and 'df_dados_apont' in st.session_state and st.session_state.df_dados_apont is not None:
        df_apont = st.session_state.df_dados_apont
        df_relatorio = st.session_state.df_relatorio
        detalhes_pedido_raw = df_apont[df_apont[df_apont.columns[0]].astype(str) == str(pedido_para_buscar)].copy()
        if not detalhes_pedido_raw.empty:
            datas_pcp = df_relatorio[['ORDEN SAP', 'PREVISTO PCP']].drop_duplicates(subset=['ORDEN SAP'])
            resultado_mesclado = pd.merge(detalhes_pedido_raw, datas_pcp, how='left', left_on=detalhes_pedido_raw.columns[0], right_on='ORDEN SAP')
            NOME_REAL_COLUNA_TIPO_PECA = 'Tipo Peça'
            if NOME_REAL_COLUNA_TIPO_PECA in resultado_mesclado.columns:
                df_detalhes_pedido = resultado_mesclado[['Pedido', NOME_REAL_COLUNA_TIPO_PECA, 'PREVISTO PCP']]
                df_detalhes_pedido = df_detalhes_pedido.rename(columns={NOME_REAL_COLUNA_TIPO_PECA: 'Tipo Peça', 'PREVISTO PCP': 'Data Previsão (PCP)'})
                df_detalhes_pedido['Data Previsão (PCP)'].fillna('-', inplace=True)
                st.write("Detalhes do Pedido:")
                st.dataframe(df_detalhes_pedido, hide_index=True)

    st.divider()
    if st.button("🚀 Enviar Relatório Automaticamente por E-mail", type="primary"):
        if not df_filtrado_relatorio.empty:
            subject = f"Relatório: {filtro_selecionado} - {pd.Timestamp.now().strftime('%d/%m/%Y')}"
            with st.spinner("Enviando e-mail..."):
                if send_email_via_smtp(df_filtrado_relatorio, df_detalhes_pedido, "mdornelas@agpglass.com", subject):
                    st.success("Sucesso! O e-mail foi enviado diretamente.")
        else:
            st.warning("Não há dados no relatório principal para enviar por e-mail.")