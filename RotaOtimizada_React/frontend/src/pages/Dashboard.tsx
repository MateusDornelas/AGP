import { useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "../components/Sidebar";
import ResumeCards from "../components/ResumeCards";
import DataTable from "../components/DataTable";
import Warnings from "../components/Warnings";
import MapView from "../components/MapView";
import ChatBox from "../components/ChatBox";
import { optimize, reoptimize } from "../api/client";
import {
  ClienteEntrada,
  OtimizacaoResposta,
  ReoptimizePayload,
} from "../api/types";
import { montarColorMap } from "../lib/colors";

interface Props {
  usuario: string;
  onLogout: () => void;
}

const PASSOS_PROGRESSO: { aposSeg: number; texto: string; icone: string }[] = [
  { aposSeg: 0, icone: "📖", texto: "Lendo e normalizando a planilha…" },
  { aposSeg: 2, icone: "📍", texto: "Geocodificando endereços via Nominatim (~1s por endereço novo, cache acelera os repetidos)…" },
  { aposSeg: 25, icone: "🧠", texto: "Resolvendo CVRP com OR-Tools (capacidade + KM + janela 18:00)…" },
  { aposSeg: 55, icone: "🗺️", texto: "Calculando rotas reais no OSRM e montando o mapa…" },
  { aposSeg: 90, icone: "✅", texto: "Finalizando — quase lá…" },
];

/** Constrói o `arranjo` (Record<vucLabel, ClienteEntrada[]>) a partir da
 * resposta do backend. Usa table como fonte de verdade dos campos. */
function construirArranjo(
  resp: OtimizacaoResposta
): Record<string, ClienteEntrada[]> {
  const out: Record<string, ClienteEntrada[]> = {};
  for (const v of resp.vucs) out[v.label] = [];
  for (const linha of resp.table) {
    const dst = out[linha.rota_vuc];
    if (!dst) continue;
    dst.push({
      nome: linha.cliente,
      endereco: linha.endereco,
      lat: linha.lat,
      lon: linha.lon,
      pos: linha.pos,
      pb_ts: linha.pb_ts,
      pecas_g: linha.grandes,
      pecas_m: linha.medias,
      total: linha.total,
    });
  }
  return out;
}

export default function Dashboard({ usuario, onLogout }: Props) {
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [modo, setModo] = useState("Modelo Padrão");
  const [processando, setProcessando] = useState(false);
  const [reotimizando, setReotimizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resp, setResp] = useState<OtimizacaoResposta | null>(null);
  const [arranjo, setArranjo] = useState<Record<string, ClienteEntrada[]>>({});
  const [dirty, setDirty] = useState(false);

  const [passoIdx, setPassoIdx] = useState(0);
  const [tempoDecorrido, setTempoDecorrido] = useState(0);
  const inicioRef = useRef<number>(0);

  useEffect(() => {
    if (!processando) {
      setPassoIdx(0);
      setTempoDecorrido(0);
      return;
    }
    inicioRef.current = Date.now();
    const tick = setInterval(() => {
      const seg = Math.floor((Date.now() - inicioRef.current) / 1000);
      setTempoDecorrido(seg);
      let idx = 0;
      for (let i = PASSOS_PROGRESSO.length - 1; i >= 0; i--) {
        if (seg >= PASSOS_PROGRESSO[i].aposSeg) {
          idx = i;
          break;
        }
      }
      setPassoIdx(idx);
    }, 500);
    return () => clearInterval(tick);
  }, [processando]);

  async function handleOtimizar() {
    if (!arquivo) return;
    setErro(null);
    setProcessando(true);
    setResp(null);
    setArranjo({});
    setDirty(false);
    try {
      const r = await optimize(arquivo, modo);
      setResp(r);
      setArranjo(construirArranjo(r));
    } catch (err: any) {
      setErro(err.message || "Erro inesperado");
    } finally {
      setProcessando(false);
    }
  }

  /** Troca dois clientes de posição (mesmo VUC ou VUCs diferentes). */
  function handleSwap(
    fromVuc: string,
    fromIdx: number,
    toVuc: string,
    toIdx: number,
  ) {
    setArranjo((prev) => {
      const novo: Record<string, ClienteEntrada[]> = {};
      for (const [k, v] of Object.entries(prev)) novo[k] = [...v];
      const a = novo[fromVuc][fromIdx];
      const b = novo[toVuc][toIdx];
      if (!a || !b) return prev;
      novo[fromVuc][fromIdx] = b;
      novo[toVuc][toIdx] = a;
      return novo;
    });
    setDirty(true);
  }

  /** Move cliente sem troca — sai do origem, vai pro final do destino. */
  function handleMover(fromVuc: string, fromIdx: number, toVuc: string) {
    if (fromVuc === toVuc) return;
    setArranjo((prev) => {
      const novo: Record<string, ClienteEntrada[]> = {};
      for (const [k, v] of Object.entries(prev)) novo[k] = [...v];
      const cliente = novo[fromVuc][fromIdx];
      if (!cliente) return prev;
      novo[fromVuc] = novo[fromVuc].filter((_, i) => i !== fromIdx);
      novo[toVuc] = [...novo[toVuc], cliente];
      return novo;
    });
    setDirty(true);
  }

  /** Reordena dentro do mesmo VUC. delta = -1 sobe, +1 desce. */
  function handleReordenar(vuc: string, idx: number, delta: number) {
    setArranjo((prev) => {
      const lista = prev[vuc];
      if (!lista) return prev;
      const novoIdx = idx + delta;
      if (novoIdx < 0 || novoIdx >= lista.length) return prev;
      const reord = [...lista];
      [reord[idx], reord[novoIdx]] = [reord[novoIdx], reord[idx]];
      return { ...prev, [vuc]: reord };
    });
    setDirty(true);
  }

  async function handleReotimizar() {
    setErro(null);
    setReotimizando(true);
    try {
      const payload: ReoptimizePayload = {
        vucs: Object.entries(arranjo)
          .filter(([, cs]) => cs.length > 0)
          .map(([label, cs]) => ({ label, clientes: cs })),
      };
      const r = await reoptimize(payload);
      setResp(r);
      setArranjo(construirArranjo(r));
      setDirty(false);
    } catch (err: any) {
      setErro(err.message || "Erro na reotimização");
    } finally {
      setReotimizando(false);
    }
  }

  // Conta quantos clientes mudaram de posição/VUC em relação ao
  // último resp aplicado. Mostrado como "X mudança(s) pendente(s)".
  const mudancasPendentes = useMemo(() => {
    if (!resp || !dirty) return 0;
    const baseline = construirArranjo(resp);
    let n = 0;
    for (const label of Object.keys(arranjo)) {
      const a = arranjo[label] ?? [];
      const b = baseline[label] ?? [];
      for (let i = 0; i < Math.max(a.length, b.length); i++) {
        if (a[i]?.nome !== b[i]?.nome) n++;
      }
    }
    return n;
  }, [resp, arranjo, dirty]);

  function handleDescartar() {
    if (!resp) return;
    setArranjo(construirArranjo(resp));
    setDirty(false);
  }

  // Para o mapa: enquanto dirty, mostra o arranjo proposto (chegada = "—")
  const vucsParaMapa = useMemo(() => {
    if (!resp) return null;
    if (!dirty) return resp;
    return {
      ...resp,
      vucs: Object.entries(arranjo)
        .filter(([, cs]) => cs.length > 0)
        .map(([label, cs]) => ({
          label,
          paradas: cs.map((c, i) => ({
            seq: i + 1,
            cliente: c.nome,
            lat: c.lat,
            lon: c.lon,
            endereco: c.endereco,
            chegada: "—",
          })),
        })),
      table: Object.entries(arranjo).flatMap(([label, cs]) =>
        cs.map((c, i) => ({
          rota_vuc: label,
          seq: i + 1,
          chegada: "—",
          cliente: c.nome,
          pos: c.pos,
          pb_ts: c.pb_ts,
          grandes: c.pecas_g,
          medias: c.pecas_m,
          total: c.total,
          endereco: c.endereco,
          lat: c.lat,
          lon: c.lon,
        }))
      ),
    } as OtimizacaoResposta;
  }, [resp, arranjo, dirty]);

  // Color map global: label do VUC → cor (consistência mapa/tabela/cards)
  const colorMap = useMemo(
    () =>
      vucsParaMapa
        ? montarColorMap(vucsParaMapa.vucs.map((v) => v.label))
        : {},
    [vucsParaMapa]
  );

  const passoAtual = PASSOS_PROGRESSO[passoIdx];

  return (
    <div className="flex min-h-screen bg-agp-bg text-gray-100">
      <Sidebar
        usuario={usuario}
        modo={modo}
        arquivo={arquivo}
        processando={processando}
        onArquivoChange={setArquivo}
        onModoChange={setModo}
        onOtimizar={handleOtimizar}
        onLogout={onLogout}
      />

      <main className="flex-1 overflow-y-auto">
        <header className="border-b border-agp-border bg-agp-surface/60 backdrop-blur sticky top-0 z-[1000]">
          <div className="px-6 py-4 flex items-center gap-4">
            <div>
              <h1 className="text-lg font-semibold leading-tight">
                🚛 Otimizador Logístico Inteligente
              </h1>
              <p className="text-xs text-agp-muted">
                Roteirização inteligente · CVRP + IA · troca interativa
              </p>
            </div>
            <span className="ml-auto text-xs text-agp-muted hidden sm:inline">
              AGP Glass
            </span>
          </div>
        </header>

        <div className="px-6 py-6 space-y-5">
          {erro && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-300 rounded-lg px-4 py-3 text-sm">
              {erro}
            </div>
          )}

          {!resp && !processando && (
            <div className="bg-agp-surface border border-dashed border-agp-border rounded-2xl p-10 text-center text-agp-muted text-sm">
              Suba uma planilha e clique em{" "}
              <strong className="text-agp-blue">Gerar Otimização</strong>.
            </div>
          )}

          {processando && (
            <div className="bg-agp-surface border border-agp-border rounded-2xl p-6 space-y-4">
              <div className="flex items-center gap-3 text-base">
                <span className="inline-block animate-pulse text-2xl">
                  {passoAtual.icone}
                </span>
                <span className="text-gray-100">{passoAtual.texto}</span>
              </div>
              <div className="space-y-1">
                {PASSOS_PROGRESSO.map((p, i) => {
                  const ativo = i === passoIdx;
                  const concluido = i < passoIdx;
                  return (
                    <div
                      key={i}
                      className={`flex items-center gap-2 text-xs ${
                        ativo
                          ? "text-agp-blue font-semibold"
                          : concluido
                          ? "text-agp-muted line-through"
                          : "text-agp-muted/50"
                      }`}
                    >
                      <span>{concluido ? "✓" : ativo ? "▸" : "·"}</span>
                      <span>{p.texto}</span>
                    </div>
                  );
                })}
              </div>
              <div className="text-xs text-agp-muted pt-2 border-t border-agp-border">
                ⏱️ {tempoDecorrido}s decorridos · execução típica fica entre
                30s e 2 min (depende do tamanho da planilha e do cache de
                geocoding)
              </div>
            </div>
          )}

          {resp && (
            <>
              <div className="bg-agp-surface border border-agp-border rounded-2xl px-5 py-4 text-sm flex flex-wrap gap-x-6 gap-y-1">
                <span>
                  Modo executado:{" "}
                  <strong className="text-agp-blue">
                    {resp.modo_efetivo}
                  </strong>
                </span>
                <span>
                  VUCs: <strong>{resp.vucs.length}</strong>
                </span>
                <span>
                  Paradas: <strong>{resp.table.length}</strong>
                </span>
              </div>

              {resp.aviso_fallback && (
                <div className="bg-orange-500/10 border border-orange-500/30 text-orange-200 rounded-xl px-4 py-3 text-sm">
                  🔧 <strong>Fallback ativado.</strong> {resp.aviso_fallback}
                </div>
              )}

              {(dirty || reotimizando) && (
                <div className="bg-agp-blue/10 border border-agp-blue/40 rounded-xl px-4 py-3 text-sm flex items-center gap-3 sticky top-[68px] z-[900] backdrop-blur">
                  <span className={`text-agp-blue text-lg ${reotimizando ? "animate-pulse" : ""}`}>
                    {reotimizando ? "⏳" : "✏️"}
                  </span>
                  <span className="flex-1 text-gray-200">
                    {reotimizando ? (
                      "Recalculando KM, tempo e rotas reais via OSRM…"
                    ) : (
                      <>
                        <strong className="text-agp-blue">
                          {mudancasPendentes} mudança{mudancasPendentes === 1 ? "" : "s"} pendente{mudancasPendentes === 1 ? "" : "s"}
                        </strong>
                        {" — continue ajustando ou clique em "}
                        <strong>Reotimizar agora</strong>
                        {" pra aplicar tudo de uma vez."}
                      </>
                    )}
                  </span>
                  {dirty && !reotimizando && (
                    <>
                      <button
                        onClick={handleDescartar}
                        className="text-xs border border-agp-border text-agp-muted hover:text-white px-3 py-1.5 rounded-lg transition"
                      >
                        Desfazer tudo
                      </button>
                      <button
                        onClick={handleReotimizar}
                        className="text-xs bg-agp-blue hover:brightness-110 text-black font-semibold px-4 py-1.5 rounded-lg transition shadow"
                      >
                        🔄 Reotimizar agora
                      </button>
                    </>
                  )}
                </div>
              )}

              <Warnings resp={resp} />

              <ResumeCards
                arranjo={arranjo}
                stats={resp.stats}
                colorMap={colorMap}
                dirty={dirty}
                onSwap={handleSwap}
                onMover={handleMover}
                onReordenar={handleReordenar}
              />

              {vucsParaMapa && <MapView resp={vucsParaMapa} />}

              <DataTable rows={resp.table} colorMap={colorMap} />

              <ChatBox resp={resp} />
            </>
          )}
        </div>
      </main>
    </div>
  );
}
