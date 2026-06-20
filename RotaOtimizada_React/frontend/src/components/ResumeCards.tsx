import { useState } from "react";
import { ClienteEntrada, StatsVuc } from "../api/types";

interface Props {
  arranjo: Record<string, ClienteEntrada[]>;
  stats: Record<string, StatsVuc>;
  colorMap: Record<string, string>;
  dirty: boolean;
  /** Troca dois clientes (cada um vai pra posição do outro). */
  onSwap: (
    fromVuc: string, fromIdx: number,
    toVuc: string, toIdx: number,
  ) => void;
  /** Move o cliente sem troca — vai pro fim do VUC destino. */
  onMover: (fromVuc: string, fromIdx: number, toVuc: string) => void;
  /** Reordena dentro do mesmo VUC (delta = -1 sobe, +1 desce). */
  onReordenar: (vuc: string, idx: number, delta: number) => void;
}

interface ClienteItemProps {
  cliente: ClienteEntrada;
  vucLabel: string;
  idx: number;
  total: number; // total de clientes no VUC (pra desabilitar reordenar nas bordas)
  selecionado: boolean;
  todosCandidatos: { vucLabel: string; idx: number; cliente: ClienteEntrada }[];
  outrosVucs: { label: string; tamanho: number }[];
  colorMap: Record<string, string>;
  onClick: () => void;
  onSwap: (toVuc: string, toIdx: number) => void;
  onMover: (toVuc: string) => void;
  onReordenar: (delta: number) => void;
  onClose: () => void;
}

function ClienteItem({
  cliente, vucLabel, idx, total, selecionado,
  todosCandidatos, outrosVucs, colorMap,
  onClick, onSwap, onMover, onReordenar, onClose,
}: ClienteItemProps) {
  const cor = colorMap[vucLabel];
  return (
    <li className="rounded-md">
      <button
        type="button"
        onClick={onClick}
        className={`w-full flex items-center gap-2 px-2 py-1 rounded-md text-xs text-left transition ${
          selecionado
            ? "bg-agp-blue/20 ring-1 ring-agp-blue/60"
            : "hover:bg-agp-card/70"
        }`}
        title="Clique para editar este cliente"
      >
        <span className="text-agp-muted">{idx + 1}.</span>
        <span className="text-gray-200 truncate flex-1">{cliente.nome}</span>
        <span className="font-mono" style={{ color: cor }}>
          {cliente.total}
        </span>
      </button>

      {selecionado && (
        <div className="mt-1 mb-2 p-3 bg-agp-card border border-agp-blue/40 rounded-md space-y-3 text-xs">
          <div className="text-agp-muted">
            Editando:{" "}
            <strong className="text-gray-100">{cliente.nome}</strong>
          </div>

          {/* --- TROCAR --- */}
          <div className="space-y-1">
            <div className="text-agp-muted text-[10px] uppercase tracking-wide">
              ↔ Trocar de posição com outro cliente
            </div>
            <select
              defaultValue=""
              onChange={(e) => {
                const v = e.target.value;
                if (!v) return;
                const [toVuc, toIdxStr] = v.split("::");
                onSwap(toVuc, parseInt(toIdxStr, 10));
              }}
              className="w-full bg-agp-bg border border-agp-border rounded-md px-2 py-1.5 text-xs text-gray-100 focus:outline-none focus:ring-2 focus:ring-agp-blue"
            >
              <option value="">— escolha um cliente —</option>
              {todosCandidatos.map((c) => {
                const corCand = colorMap[c.vucLabel] ?? "#fff";
                return (
                  <option
                    key={`swap-${c.vucLabel}::${c.idx}`}
                    value={`${c.vucLabel}::${c.idx}`}
                    style={{ color: corCand, background: "#0d0d0f" }}
                  >
                    {c.vucLabel} · Seq {c.idx + 1} · {c.cliente.nome} ({c.cliente.total} pç)
                  </option>
                );
              })}
            </select>
          </div>

          {/* --- MOVER --- */}
          {outrosVucs.length > 0 && (
            <div className="space-y-1">
              <div className="text-agp-muted text-[10px] uppercase tracking-wide">
                → Mover para o final de outro VUC
              </div>
              <select
                defaultValue=""
                onChange={(e) => {
                  const v = e.target.value;
                  if (!v) return;
                  onMover(v);
                }}
                className="w-full bg-agp-bg border border-agp-border rounded-md px-2 py-1.5 text-xs text-gray-100 focus:outline-none focus:ring-2 focus:ring-agp-blue"
              >
                <option value="">— escolha um VUC —</option>
                {outrosVucs.map((v) => {
                  const corVuc = colorMap[v.label] ?? "#fff";
                  return (
                    <option
                      key={`move-${v.label}`}
                      value={v.label}
                      style={{ color: corVuc, background: "#0d0d0f" }}
                    >
                      {v.label} ({v.tamanho} parada{v.tamanho === 1 ? "" : "s"})
                    </option>
                  );
                })}
              </select>
            </div>
          )}

          {/* --- REORDENAR --- */}
          {total > 1 && (
            <div className="space-y-1">
              <div className="text-agp-muted text-[10px] uppercase tracking-wide">
                ↕ Reordenar dentro do VUC
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={idx === 0}
                  onClick={() => onReordenar(-1)}
                  className="flex-1 bg-agp-bg border border-agp-border rounded-md px-2 py-1.5 text-gray-200 hover:border-agp-blue/60 hover:text-agp-blue disabled:opacity-30 disabled:hover:border-agp-border disabled:hover:text-gray-200 transition"
                >
                  ↑ Subir
                </button>
                <button
                  type="button"
                  disabled={idx === total - 1}
                  onClick={() => onReordenar(1)}
                  className="flex-1 bg-agp-bg border border-agp-border rounded-md px-2 py-1.5 text-gray-200 hover:border-agp-blue/60 hover:text-agp-blue disabled:opacity-30 disabled:hover:border-agp-border disabled:hover:text-gray-200 transition"
                >
                  ↓ Descer
                </button>
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={onClose}
            className="text-agp-muted hover:text-white underline"
          >
            cancelar
          </button>
        </div>
      )}
    </li>
  );
}

interface VucCardProps {
  label: string;
  cor?: string;
  clientes: ClienteEntrada[];
  stats?: StatsVuc;
  dirty: boolean;
  selected: { vucLabel: string; idx: number } | null;
  todosCandidatos: { vucLabel: string; idx: number; cliente: ClienteEntrada }[];
  outrosVucs: { label: string; tamanho: number }[];
  colorMap: Record<string, string>;
  onItemClick: (vucLabel: string, idx: number) => void;
  onSwap: (toVuc: string, toIdx: number) => void;
  onMover: (toVuc: string) => void;
  onReordenar: (delta: number) => void;
  onClose: () => void;
}

function VucCard(props: VucCardProps) {
  const { label, cor, clientes, stats, dirty, selected,
    todosCandidatos, outrosVucs, colorMap,
    onItemClick, onSwap, onMover, onReordenar, onClose } = props;
  const totalPecas = clientes.reduce((acc, c) => acc + c.total, 0);
  const overCap = totalPecas > 57;

  return (
    <div
      className="bg-agp-surface border border-agp-border rounded-2xl p-5"
      style={cor ? { borderLeft: `4px solid ${cor}` } : undefined}
    >
      <h3
        className="font-semibold text-sm mb-3 flex items-center gap-2"
        style={{ color: cor ?? "#8FC5CF" }}
      >
        {cor && (
          <span
            className="inline-block w-3 h-3 rounded-full"
            style={{ background: cor }}
          />
        )}
        {label}
      </h3>

      <div className={`space-y-1 text-sm ${dirty ? "opacity-50" : ""}`}>
        <p>
          <span className="text-agp-muted">KM:</span>{" "}
          <span className="font-mono">{stats?.km ?? "—"}</span>
        </p>
        <p>
          <span className="text-agp-muted">📦 Peças:</span>{" "}
          <span className={`font-mono ${overCap ? "text-red-300" : ""}`}>
            {totalPecas}
            {dirty ? "" : ` (${stats?.pecas ?? "?"})`}
          </span>
          {overCap && (
            <span className="ml-1 text-red-300 text-xs">⚠ acima de 57</span>
          )}
        </p>
        <p>
          <span className="text-agp-muted">⏱️ Tempo:</span>{" "}
          <span className="font-mono">{stats?.tempo_label ?? "—"}</span>
        </p>
      </div>

      <p className="text-xs font-semibold mt-3 mb-1 text-agp-muted uppercase tracking-wide">
        Clientes ({clientes.length})
      </p>

      <ul className="text-xs space-y-0.5 min-h-[40px]">
        {clientes.length === 0 ? (
          <li className="italic text-agp-muted px-2 py-2 border border-dashed border-agp-border rounded-md text-center">
            Sem clientes
          </li>
        ) : (
          clientes.map((c, i) => {
            const isSelected =
              selected !== null &&
              selected.vucLabel === label &&
              selected.idx === i;
            return (
              <ClienteItem
                key={`${label}-${c.nome}-${i}`}
                cliente={c}
                vucLabel={label}
                idx={i}
                total={clientes.length}
                selecionado={isSelected}
                todosCandidatos={todosCandidatos.filter(
                  (cand) => !(cand.vucLabel === label && cand.idx === i)
                )}
                outrosVucs={outrosVucs.filter((v) => v.label !== label)}
                colorMap={colorMap}
                onClick={() => onItemClick(label, i)}
                onSwap={onSwap}
                onMover={onMover}
                onReordenar={onReordenar}
                onClose={onClose}
              />
            );
          })
        )}
      </ul>
    </div>
  );
}

export default function ResumeCards({
  arranjo, stats, colorMap, dirty, onSwap, onMover, onReordenar,
}: Props) {
  const [selected, setSelected] = useState<{
    vucLabel: string;
    idx: number;
  } | null>(null);

  const entries = Object.entries(arranjo);
  if (entries.length === 0) return null;

  // Lookup global pra dropdown de troca
  const todosCandidatos = entries.flatMap(([vucLabel, cs]) =>
    cs.map((cliente, idx) => ({ vucLabel, idx, cliente }))
  );
  const outrosVucs = entries.map(([label, cs]) => ({
    label,
    tamanho: cs.length,
  }));

  function handleItemClick(vucLabel: string, idx: number) {
    if (
      selected !== null &&
      selected.vucLabel === vucLabel &&
      selected.idx === idx
    ) {
      setSelected(null);
    } else {
      setSelected({ vucLabel, idx });
    }
  }

  function handleSwap(toVuc: string, toIdx: number) {
    if (!selected) return;
    onSwap(selected.vucLabel, selected.idx, toVuc, toIdx);
    setSelected(null);
  }

  function handleMover(toVuc: string) {
    if (!selected) return;
    onMover(selected.vucLabel, selected.idx, toVuc);
    setSelected(null);
  }

  function handleReordenar(delta: number) {
    if (!selected) return;
    onReordenar(selected.vucLabel, selected.idx, delta);
    // Mantém o cliente selecionado mas atualiza o idx
    setSelected({
      vucLabel: selected.vucLabel,
      idx: selected.idx + delta,
    });
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-100">
          📊 Resumo da Frota
        </h2>
        <span className="text-xs text-agp-muted">
          💡 Clique num cliente para trocar, mover ou reordenar
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {entries.map(([label, clientes]) => (
          <VucCard
            key={label}
            label={label}
            cor={colorMap[label]}
            clientes={clientes}
            stats={stats[label]}
            dirty={dirty}
            selected={selected}
            todosCandidatos={todosCandidatos}
            outrosVucs={outrosVucs}
            colorMap={colorMap}
            onItemClick={handleItemClick}
            onSwap={handleSwap}
            onMover={handleMover}
            onReordenar={handleReordenar}
            onClose={() => setSelected(null)}
          />
        ))}
      </div>
    </section>
  );
}
