import { useState, useRef, useEffect, FormEvent } from "react";
import { chat } from "../api/client";
import { ChatMessage, OtimizacaoResposta } from "../api/types";

interface Props {
  resp: OtimizacaoResposta | null;
}

/** Monta o CSV de contexto + RESUMO POR VEÍCULO igual ao Streamlit v3. */
function montarContexto(resp: OtimizacaoResposta | null): string {
  if (!resp || resp.table.length === 0) return "Nenhuma rota gerada ainda.";

  const headers = [
    "Rota/VUC", "Seq", "Chegada", "Cliente",
    "POS", "PB/TS", "Grandes", "Médias", "Total", "Endereço",
  ];
  const linhas = [headers.join(",")];
  for (const r of resp.table) {
    linhas.push(
      [
        r.rota_vuc,
        r.seq,
        r.chegada,
        `"${r.cliente.replace(/"/g, '""')}"`,
        r.pos,
        r.pb_ts,
        r.grandes,
        r.medias,
        r.total,
        `"${r.endereco.replace(/"/g, '""')}"`,
      ].join(",")
    );
  }
  let ctx = linhas.join("\n");

  if (resp.stats && Object.keys(resp.stats).length > 0) {
    ctx += "\n\nRESUMO POR VEÍCULO:";
    for (const [label, s] of Object.entries(resp.stats)) {
      ctx += `\n- ${label}: ${s.km}km | ${s.pecas} peças | `
        + `Racks: ${s.racks} | Tempo: ${s.tempo_label} | `
        + `Custo: R$ ${s.custo}`;
    }
  }
  return ctx;
}

export default function ChatBox({ resp }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, enviando]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || enviando) return;

    const novasMsgs: ChatMessage[] = [
      ...messages,
      { role: "user", content: trimmed },
    ];
    setMessages(novasMsgs);
    setInput("");
    setErro(null);
    setEnviando(true);

    try {
      const r = await chat({
        messages: novasMsgs,
        route_context: montarContexto(resp),
      });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: r.resposta },
      ]);
    } catch (err: any) {
      setErro(err.message || "Erro inesperado");
    } finally {
      setEnviando(false);
    }
  }

  function handleLimpar() {
    setMessages([]);
    setErro(null);
  }

  return (
    <section className="bg-agp-surface border border-agp-border rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-100">
          🤖 Chat com IA (Claude)
        </h2>
        {messages.length > 0 && (
          <button
            onClick={handleLimpar}
            className="text-xs text-agp-muted hover:text-white border border-agp-border rounded-lg px-3 py-1 transition"
          >
            Limpar conversa
          </button>
        )}
      </div>

      <p className="text-xs text-agp-muted">
        Tire dúvidas sobre as rotas, peça reotimizações em texto ou
        simule cenários (chuva, descarga lenta, janela apertada, capacidade
        diferente). Claude conhece os VUCs gerados nesta sessão.
      </p>

      <div
        ref={scrollRef}
        className="bg-agp-bg border border-agp-border rounded-xl p-3 h-80 overflow-y-auto space-y-3"
      >
        {messages.length === 0 && (
          <div className="text-agp-muted text-sm text-center py-12">
            {resp
              ? "Faça uma pergunta sobre as rotas geradas."
              : "Gere uma otimização primeiro pra eu ter contexto sobre os VUCs."}
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap font-mono ${
                m.role === "user"
                  ? "bg-agp-blue/15 border border-agp-blue/40 text-gray-100"
                  : "bg-agp-card border border-agp-border text-gray-200"
              }`}
              style={{ fontFamily: m.role === "user" ? undefined : "ui-monospace, monospace", fontSize: 13 }}
            >
              {m.content}
            </div>
          </div>
        ))}
        {enviando && (
          <div className="flex justify-start">
            <div className="bg-agp-card border border-agp-border rounded-xl px-3 py-2 text-sm text-agp-muted animate-pulse">
              Claude pensando…
            </div>
          </div>
        )}
      </div>

      {erro && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-300 rounded-lg px-3 py-2 text-xs">
          ⚠ {erro}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Dúvida sobre as rotas?"
          disabled={enviando}
          className="flex-1 bg-agp-bg border border-agp-border rounded-xl px-3 py-2 text-sm text-gray-100 placeholder:text-agp-muted focus:outline-none focus:border-agp-blue/60 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={enviando || !input.trim()}
          className="bg-agp-blue hover:brightness-110 text-black font-semibold px-5 py-2 rounded-xl transition disabled:opacity-50"
        >
          {enviando ? "…" : "Enviar"}
        </button>
      </form>
    </section>
  );
}
