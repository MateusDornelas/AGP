import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai
import numpy as np
from pandas.api.types import is_numeric_dtype

# --- Configuração da Página ---
st.set_page_config(
    page_title="IA - Análise Consumo",
    page_icon="🤖",
    layout="wide"
)

# --- Configuração da API do Google Gemini ---
# (Seu código da API permanece o mesmo)
try:
    # Lembre-se de colocar sua chave de API válida aqui
    GOOGLE_API_KEY = "SUA_CHAVE_API_AQUI" # Substitua pela sua chave
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('models/gemini-flash-latest')
    gemini_configurado = True
except Exception as e:
    # Para o exemplo, vamos desabilitar o erro se a chave não for encontrada
    # st.error(f"Ocorreu um erro ao configurar a API do Google: {e}")
    gemini_configurado = False


# --- Título, Imagem e Descrição ---
st.title("🤖 IA - Análise Consumo")
# st.image("AGP.jpg", width=300) # Removido para execução sem a imagem local
st.write("Faça o upload de um arquivo Excel para visualizar os dados e conversar com um assistente de IA.")

# --- Nomes das Colunas Esperadas ---
COLUNA_MATERIAL = "Texto breve material"
COLUNA_QUANTIDADE = "Quantidade"
COLUNA_DATA = "Data de lançamento"

# --- Função para calcular métricas ---
def calcular_metricas(df_para_analise, df_completo):
    """Calcula as métricas de consumo para os materiais filtrados."""
    data_mais_recente = df_completo[COLUNA_DATA].max()
    data_inicio_2_meses = data_mais_recente - pd.DateOffset(months=2)
    
    materiais_unicos = df_para_analise[COLUNA_MATERIAL].unique()
    
    lista_metricas = []

    for material in materiais_unicos:
        df_material = df_completo[df_completo[COLUNA_MATERIAL] == material].copy()
        df_material[COLUNA_QUANTIDADE] = df_material[COLUNA_QUANTIDADE].abs()
        
        total_anual = df_material[COLUNA_QUANTIDADE].sum()
        semanas_no_ano = 52.14
        media_semanal_anual = total_anual / semanas_no_ano
        
        df_ultimos_2_meses = df_material[df_material[COLUNA_DATA] >= data_inicio_2_meses]
        total_ultimos_2_meses = df_ultimos_2_meses[COLUNA_QUANTIDADE].sum()
        semanas_no_periodo = (data_mais_recente - data_inicio_2_meses).days / 7
        if semanas_no_periodo < 1: semanas_no_periodo = 1
        media_semanal_2_meses = total_ultimos_2_meses / semanas_no_periodo

        if media_semanal_anual > 0:
            variacao_percentual = ((media_semanal_2_meses - media_semanal_anual) / media_semanal_anual) * 100
        else:
            variacao_percentual = np.inf
            
        lista_metricas.append({
            "Material": material,
            "Média Semanal (Anual)": media_semanal_anual,
            "Média Semanal (Últimos 2 Meses)": media_semanal_2_meses,
            "% Variação": variacao_percentual
        })
        
    return pd.DataFrame(lista_metricas)

# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Escolha um arquivo Excel (.xlsx)", type="xlsx")

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.session_state.df_original = df

        # --- Limpeza e Preparação dos Dados ---
        colunas_necessarias = [COLUNA_MATERIAL, COLUNA_QUANTIDADE, COLUNA_DATA]
        if not all(col in df.columns for col in colunas_necessarias):
            st.error(f"Erro: O arquivo precisa conter as colunas: {', '.join(colunas_necessarias)}")
            st.stop()
        
        df[COLUNA_QUANTIDADE] = pd.to_numeric(df[COLUNA_QUANTIDADE], errors='coerce').fillna(0)
        df[COLUNA_DATA] = pd.to_datetime(df[COLUNA_DATA], errors='coerce')
        df.dropna(subset=[COLUNA_DATA], inplace=True)
        df['Mês'] = df[COLUNA_DATA].dt.strftime('%Y-%m')
        
        st.success("Arquivo processado com sucesso! Configure seus filtros abaixo.")

        # --- Filtros na Barra Lateral ---
        st.sidebar.header("Filtros")
        lista_materiais = ["Todos"] + sorted(df[COLUNA_MATERIAL].unique().tolist())
        material_filtrado = st.sidebar.selectbox("Selecione um Material:", lista_materiais)
        lista_meses = ["Todos"] + sorted(df['Mês'].unique().tolist(), reverse=True)
        mes_filtrado = st.sidebar.selectbox("Selecione um Mês:", lista_meses)
        
        # ### BOA PRÁTICA ###: Mover o botão para o final e usar st.session_state
        # para manter o estado dos filtros de forma mais robusta.
        # Sua implementação atual já está boa, então manteremos.
        if st.sidebar.button("Aplicar Filtros"):
            df_filtrado = df.copy()
            if material_filtrado != "Todos":
                df_filtrado = df_filtrado[df_filtrado[COLUNA_MATERIAL] == material_filtrado]
            if mes_filtrado != "Todos":
                df_filtrado = df_filtrado[df_filtrado['Mês'] == mes_filtrado]
            
            st.session_state.df_filtrado = df_filtrado
            st.session_state.filtros_aplicados = {'material': material_filtrado, 'mes': mes_filtrado}

        if 'df_filtrado' in st.session_state:
            df_filtrado = st.session_state.df_filtrado
            filtros = st.session_state.filtros_aplicados

            tab1, tab2 = st.tabs(["📊 Gráficos e Dados", "💬 Chatbot com IA"])

            with tab1:
                st.header(f"Análise para: {filtros['material']} | Mês: {filtros['mes']}")
                if df_filtrado.empty:
                    st.warning("Nenhum dado encontrado para os filtros selecionados.")
                else:
                    st.subheader("Métricas de Consumo")
                    df_metricas = calcular_metricas(df_filtrado, st.session_state.df_original)
                    
                    ### ALTERAÇÃO ###: Definição de um dicionário para formatação. É mais limpo.
                    formatters = {
                        "Média Semanal (Anual)": "{:,.2f}",
                        "Média Semanal (Últimos 2 Meses)": "{:,.2f}",
                        "% Variação": "{:+.2f}%" # Adicionado sinal de + para variações positivas
                    }
                    st.dataframe(df_metricas.style.format(formatters))

                    df_filtrado_abs = df_filtrado.copy()
                    df_filtrado_abs[COLUNA_QUANTIDADE] = df_filtrado_abs[COLUNA_QUANTIDADE].abs()

                    st.subheader("Consumo Total por Material")
                    consumo_total = df_filtrado_abs.groupby(COLUNA_MATERIAL)[COLUNA_QUANTIDADE].sum().sort_values(ascending=False)
                    
                    ### ALTERAÇÃO ###: Adicionada a formatação do texto e dos eixos.
                    fig_bar = px.bar(consumo_total, 
                                     x=consumo_total.index, 
                                     y=consumo_total.values, 
                                     text_auto='.2s', # Formata o texto na barra (ex: 1.23M)
                                     labels={'x': 'Material', 'y': 'Quantidade Total'})
                    fig_bar.update_traces(textposition='outside')
                    fig_bar.update_layout(yaxis_tickformat=',.0f') # Formata o eixo Y com separador de milhar
                    st.plotly_chart(fig_bar, use_container_width=True)


                    st.subheader("Consumo Mensal por Material")
                    consumo_mensal_material = df_filtrado_abs.groupby(['Mês', COLUNA_MATERIAL])[COLUNA_QUANTIDADE].sum().reset_index()
                    
                    ### ALTERAÇÃO ###: Adicionada a formatação dos eixos e do hover.
                    fig_mensal = px.bar(
                        consumo_mensal_material,
                        x='Mês',
                        y=COLUNA_QUANTIDADE,
                        color=COLUNA_MATERIAL,
                        title="Consumo Detalhado por Mês e Material",
                        labels={'Mês': 'Mês', COLUNA_QUANTIDADE: 'Consumo Total', COLUNA_MATERIAL: 'Material'}
                    )
                    fig_mensal.update_layout(yaxis_tickformat=',.0f') # Formata o eixo Y com separador de milhar
                    st.plotly_chart(fig_mensal, use_container_width=True)
                    

                    st.subheader("Consumo Diário")
                    consumo_diario = df_filtrado_abs.groupby(df_filtrado_abs[COLUNA_DATA].dt.date)[COLUNA_QUANTIDADE].sum()
                    
                    ### ALTERAÇÃO ###: Adicionada a formatação dos eixos e do hover.
                    fig_line = px.line(consumo_diario, 
                                       x=consumo_diario.index, 
                                       y=consumo_diario.values, 
                                       markers=True, 
                                       labels={'x': 'Data', 'y': 'Consumo'})
                    # Formata o tooltip (hover) e o eixo Y
                    fig_line.update_traces(hovertemplate='Data: %{x}<br>Consumo: %{y:,.0f}')
                    fig_line.update_layout(yaxis_tickformat=',.0f')
                    st.plotly_chart(fig_line, use_container_width=True)
                    
            with tab2:
                # O chatbot continua funcionando com os dados filtrados
                st.header("Converse com o Chatbot para tirar suas dúvidas")
                if not gemini_configurado: st.warning("O chatbot está desativado pois a chave da API não foi configurada.")
                else:
                    if "messages" not in st.session_state: st.session_state.messages = []
                    for message in st.session_state.messages:
                        with st.chat_message(message["role"]): st.markdown(message["content"])
                    if prompt := st.chat_input("Faça uma pergunta sobre os dados filtrados..."):
                        st.session_state.messages.append({"role": "user", "content": prompt})
                        with st.chat_message("user"): st.markdown(prompt)
                        with st.chat_message("assistant"):
                            message_placeholder = st.empty()
                            message_placeholder.markdown("Analisando os dados e pensando... 🧠")
                            dados_csv = st.session_state.df_filtrado.head(500).to_csv(index=False)
                            prompt_completo = f"Você é um analista de dados senior. Analise os seguintes dados que JÁ FORAM FILTRADOS pelo usuário:\n--- DADOS ---\n{dados_csv}\n--- FIM DOS DADOS ---\nCom base SOMENTE nestes dados, responda à pergunta: \"{prompt}\""
                            response = model.generate_content(prompt_completo)
                            message_placeholder.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao processar o arquivo: {e}")
else:
    st.info("Aguardando o upload de um arquivo Excel para começar a análise.")