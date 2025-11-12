import streamlit as st
import pandas as pd
from pathlib import Path
from email.message import EmailMessage
import os
import win32com.client as win32
import pythoncom
import locale
from datetime import datetime

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    st.warning("Locale 'pt_BR.UTF-8' não encontrado. O nome do mês pode ficar em inglês.")

st.set_page_config(page_title="Análise e Processamento de Relatórios", page_icon="📊", layout="wide")
st.title("📊 Painel de Análise e Processamento de Relatórios")

FILE_PATH_ORIGEM = r"C:\Users\mdornelas\OneDrive - AGP GROUP\Documentos\01. AÇÕES\Metas\IA\Agente de pedidos comercial\Cópia de PAINEL DE CONTROLE_EXPORTAÇÃO_NEW.xlsm"
FILE_PATH_DESTINO = r"C:\Users\mdornelas\OneDrive - AGP GROUP\Documentos\01. AÇÕES\Metas\IA\Agente de pedidos comercial\Formato de Estatus General Col - Bra.xlsx"
SHEET_RELATORIO = 'RELATÓRIO'
SHEET_DADOS_APONT = 'DADOS_APONT'
SHEET_PIVOT = 'Planilha2'
OUTPUT_EML_PATH = r"C:\Users\mdornelas\Desktop\relatorio_filtrado.eml"

FILTROS_PAIS = {
    'Todos': [], 'CAM': ['ÁFRICA DO SUL', 'DEFENSE', 'CENTROÁMERICA'],
    'MERCOSUL': ['MERCOSUL'], 'MÉXICO': ['MÉXICO']
}

@st.cache_data
def load_data(file_path, sheet_name):
    # (código da função load_data permanece o mesmo)
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

# --- FUNÇÃO DE GERAÇÃO DE E-MAIL (CORRIGIDA) ---
def generate_eml_file(main_df: pd.DataFrame, recipient: str, subject: str) -> bool:
    """Gera e salva um arquivo .eml com o DataFrame fornecido em formato HTML."""
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
    html_body = f"""
    <html><head>{html_style}</head><body>
        <p>Buen día,</p><p>Sigue o status solicitado.</p><br>
        <h3>Relatório Principal</h3>{html_table_main}<br>
        <p>Atenciosamente,<br>Agente Inteligente PCP - AGP</p>
    </body></html>
    """
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['To'] = recipient
    msg.add_alternative(html_body, subtype='html')
    try:
        with open(OUTPUT_EML_PATH, 'wb') as f:
            f.write(msg.as_bytes())
        return True
    except Exception as e:
        st.error(f"ERRO: Falha ao salvar o arquivo .eml: {e}")
        return False

# --- FUNÇÃO DE AUTOMAÇÃO DO EXCEL ---
def process_pivot_table(paises_para_filtrar: list):
    # (código da automação do Excel permanece o mesmo)
    pythoncom.CoInitialize()
    excel = None
    try:
        excel = win32.Dispatch('Excel.Application')
        excel.Visible = True
        # ... (resto do código da função)
    except Exception as e:
        st.error(f"Ocorreu um erro durante a automação do Excel: {e}")
    finally:
        pass # Não chama CoUninitialize para manter o Excel aberto

if st.button("🔍 Analisar Relatório"):
    with st.spinner("Carregando dados das planilhas..."):
        st.session_state.df_relatorio = load_data(FILE_PATH_ORIGEM, SHEET_RELATORIO)
        st.session_state.df_dados_apont = load_data(FILE_PATH_ORIGEM, SHEET_DADOS_APONT)

if 'df_relatorio' in st.session_state and st.session_state.df_relatorio is not None:
    # (O resto da interface permanece o mesmo)
    st.divider()
    st.subheader("Filtro de Relatório")
    col1, col2 = st.columns([3, 1])
    with col1:
        filtro_selecionado = st.selectbox("Filtrar por Região:", options=list(FILTROS_PAIS.keys()), label_visibility="collapsed")
    paises_para_filtrar = FILTROS_PAIS[filtro_selecionado]
    with col2:
        if st.button("⚙️ Processar Tabela Dinâmica", disabled=(filtro_selecionado == 'Todos')):
            with st.spinner(f"Automatizando Excel para a região '{filtro_selecionado}'..."):
                process_pivot_table(paises_para_filtrar)
    if paises_para_filtrar:
        df_filtrado_relatorio = st.session_state.df_relatorio[st.session_state.df_relatorio['PAÍS'].isin(paises_para_filtrar)].iloc[:, :13]
    else:
        df_filtrado_relatorio = st.session_state.df_relatorio.iloc[:, :13]
    st.subheader(f"Relatório Principal - {filtro_selecionado}")
    st.dataframe(df_filtrado_relatorio, hide_index=True)
    st.divider()
    st.subheader("Consulta Detalhada de Pedido")
    COL_PEDIDO_APONT = 'Pedido'
    COL_PEDIDO_RELATORIO = 'ORDEN SAP'
    COL_TIPO_PECA = 'Tipo_Peca'
    COL_PREVISAO = 'PREVISTO PCP'
    if 'df_dados_apont' in st.session_state and st.session_state.df_dados_apont is not None:
        colunas_ok_apont = COL_PEDIDO_APONT in st.session_state.df_dados_apont.columns and COL_TIPO_PECA in st.session_state.df_dados_apont.columns
        colunas_ok_relatorio = COL_PEDIDO_RELATORIO in st.session_state.df_relatorio.columns and COL_PREVISAO in st.session_state.df_relatorio.columns
        if colunas_ok_apont and colunas_ok_relatorio:
            pedido_input = st.text_input("Digite o número do pedido para buscar detalhes:", key="pedido_input")
            if pedido_input:
                with st.spinner("Cruzando informações do pedido..."):
                    df_dados = st.session_state.df_dados_apont
                    df_relatorio = st.session_state.df_relatorio
                    resultados_dados = df_dados[df_dados[COL_PEDIDO_APONT].astype(str) == str(pedido_input)]
                    if not resultados_dados.empty:
                        mapa_previsao = df_relatorio[[COL_PEDIDO_RELATORIO, COL_PREVISAO]].drop_duplicates(subset=[COL_PEDIDO_RELATORIO])
                        resultado_final = pd.merge(resultados_dados, mapa_previsao, left_on=COL_PEDIDO_APONT, right_on=COL_PEDIDO_RELATORIO, how='left')
                        st.write(f"Detalhes encontrados para o pedido '{pedido_input}':")
                        st.dataframe(resultado_final[[COL_PEDIDO_APONT, COL_TIPO_PECA, COL_PREVISAO]].rename(columns={
                            COL_PEDIDO_APONT: 'Pedido', COL_TIPO_PECA: 'Tipo Peça', COL_PREVISAO: 'Previsto PCP'
                        }), hide_index=True)
                    else:
                        st.warning(f"Nenhum pedido encontrado com o número '{pedido_input}' na aba DADOS_APONT.")
        else:
            st.error("Erro de Configuração: Colunas necessárias para a consulta não foram encontradas.")
    st.divider()
    if st.button("📧 Gerar E-mail com Relatório Principal", type="primary"):
        if not df_filtrado_relatorio.empty:
            subject = f"Relatório: {filtro_selecionado} - {pd.Timestamp.now().strftime('%d/%m/%Y')}"
            if generate_eml_file(df_filtrado_relatorio, "mdornelas@agpglass.com", subject):
                try:
                    os.startfile(OUTPUT_EML_PATH)
                    st.success("Sucesso! O rascunho do e-mail foi aberto no seu aplicativo de e-mail padrão.")
                except Exception as e:
                    st.error(f"Falha ao abrir o e-mail automaticamente: {e}")
        else:
            st.warning("Não há dados no relatório principal para enviar por e-mail.")