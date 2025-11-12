import sys
import win32com.client as win32
import pythoncom
from datetime import datetime
import locale

# --- ESTE SCRIPT RODA DE FORMA INDEPENDENTE ---

# Configurações (copiadas do script principal)
FILE_PATH_ORIGEM = r"C:\Users\mdornelas\OneDrive - AGP GROUP\Documentos\01. AÇÕES\Metas\IA\Agente de pedidos comercial\Cópia de PAINEL DE CONTROLE_EXPORTAÇÃO_NEW.xlsm"
FILE_PATH_DESTINO = r"C:\Users\mdornelas\OneDrive - AGP GROUP\Documentos\01. AÇÕES\Metas\IA\Agente de pedidos comercial\Formato de Estatus General Col - Bra.xlsx"
SHEET_PIVOT = 'Planilha2'

def main(paises_para_filtrar: list):
    """Função principal que realiza toda a automação do Excel."""
    pythoncom.CoInitialize()
    excel = None
    try:
        excel = win32.Dispatch('Excel.Application')
        excel.Visible = True

        wb_origem = excel.Workbooks.Open(FILE_PATH_ORIGEM)
        wb_destino = excel.Workbooks.Open(FILE_PATH_DESTINO)
        
        sheet_pivot = wb_origem.Sheets(SHEET_PIVOT)
        pivot_table = sheet_pivot.PivotTables("Tabela dinâmica1")
        pivot_field = pivot_table.PivotFields("Mercado")

        pivot_field.ClearAllFilters()
        pivot_field.EnableMultiplePageItems = True
        pivot_field.VisibleItemsList = paises_para_filtrar

        pivot_table.TableRange2.Copy()

        # Configura o locale para formatar o nome do mês
        try:
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except locale.Error:
            pass # Ignora o erro se o locale não for encontrado
            
        new_sheet_name = datetime.now().strftime("%B %d").capitalize()
        
        for sheet in wb_destino.Sheets:
            if sheet.Name == new_sheet_name:
                excel.DisplayAlerts = False
                sheet.Delete()
                excel.DisplayAlerts = True
                break
        
        new_sheet = wb_destino.Sheets.Add(After=wb_destino.Sheets(wb_destino.Sheets.Count))
        new_sheet.Name = new_sheet_name
        
        new_sheet.Range("A1").Select()
        new_sheet.Paste()
        
        new_sheet.UsedRange.Columns.AutoFit()
        try:
            new_sheet.Columns(6).ColumnWidth = 40
        except Exception:
            pass

        wb_destino.Activate()
        new_sheet.Activate()
        wb_destino.Save()
        
        # O script não precisa reportar sucesso, o usuário verá o Excel.

    except Exception as e:
        # Se um erro ocorrer, podemos escrever em um arquivo de log para depuração
        with open("log_erro_excel.txt", "w") as f:
            f.write(str(e))
    
    finally:
        # Libera as referências COM antes de finalizar
        wb_origem = None
        wb_destino = None
        excel = None
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    # sys.argv[1] conterá os países passados pelo Streamlit, separados por vírgula
    if len(sys.argv) > 1:
        paises = sys.argv[1].split(',')
        main(paises)