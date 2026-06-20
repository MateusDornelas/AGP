import { useRef } from "react";

interface Props {
  usuario: string;
  modo: string;
  arquivo: File | null;
  processando: boolean;
  onArquivoChange: (f: File | null) => void;
  onModoChange: (m: string) => void;
  onOtimizar: () => void;
  onLogout: () => void;
}

export default function Sidebar({
  usuario,
  modo,
  arquivo,
  processando,
  onArquivoChange,
  onModoChange,
  onOtimizar,
  onLogout,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <aside className="w-72 shrink-0 bg-agp-surface border-r border-agp-border p-5 flex flex-col gap-5 overflow-y-auto">
      <div className="flex justify-center">
        <img src="/AGPpng.png" alt="AGP" className="h-16 object-contain" />
      </div>

      <div className="flex items-center justify-between text-xs text-agp-muted border-b border-agp-border pb-3">
        <span className="truncate">👤 {usuario || "operador"}</span>
        <button
          onClick={onLogout}
          className="text-red-400 hover:text-red-300 transition"
        >
          sair
        </button>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2 text-gray-100">📂 Operação</h3>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          className="hidden"
          onChange={(e) => onArquivoChange(e.target.files?.[0] ?? null)}
        />
        <button
          onClick={() => inputRef.current?.click()}
          className="w-full text-sm bg-agp-card border border-dashed border-agp-border rounded-xl py-3 px-3 hover:border-agp-blue/60 hover:text-agp-blue text-left text-agp-muted transition"
        >
          {arquivo ? `📄 ${arquivo.name}` : "Suba sua planilha (.xlsx/.csv)"}
        </button>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2 text-gray-100">
          🛠️ Modo de Otimização
        </h3>
        <div className="space-y-1">
          {["Modelo Padrão", "Modo Criativo"].map((opt) => (
            <label
              key={opt}
              className={`flex items-center gap-2 text-sm py-1.5 px-2 rounded-lg cursor-pointer transition ${
                modo === opt
                  ? "bg-agp-blue/10 text-agp-blue font-semibold"
                  : "text-agp-muted hover:bg-agp-card"
              }`}
            >
              <input
                type="radio"
                name="modo"
                value={opt}
                checked={modo === opt}
                onChange={() => onModoChange(opt)}
                className="accent-agp-blue"
              />
              {opt}
            </label>
          ))}
        </div>
      </div>

      <button
        onClick={onOtimizar}
        disabled={!arquivo || processando}
        className="w-full bg-agp-blue text-agp-black font-bold py-3 rounded-xl hover:opacity-90 disabled:opacity-50 transition"
      >
        {processando ? "Processando…" : "🚀 Gerar Otimização"}
      </button>
    </aside>
  );
}
