import { LinhaTabela } from "../api/types";

interface Props {
  rows: LinhaTabela[];
  /** Mapa label do VUC → cor (mesma do MapView). */
  colorMap?: Record<string, string>;
}

export default function DataTable({ rows, colorMap = {} }: Props) {
  if (rows.length === 0) return null;
  return (
    <section>
      <h2 className="text-lg font-semibold mb-3 text-gray-100">
        📋 Tabela Operacional Detalhada
      </h2>
      <div className="overflow-x-auto bg-agp-surface border border-agp-border rounded-2xl">
        <table className="w-full text-sm">
          <thead className="bg-agp-card text-left text-xs uppercase text-agp-muted tracking-wide">
            <tr>
              <th className="px-3 py-3">Rota/VUC</th>
              <th className="px-3 py-3">Seq</th>
              <th className="px-3 py-3">Chegada</th>
              <th className="px-3 py-3">Cliente</th>
              <th className="px-3 py-3 text-right">POS</th>
              <th className="px-3 py-3 text-right">PB/TS</th>
              <th className="px-3 py-3 text-right">Grandes</th>
              <th className="px-3 py-3 text-right">Médias</th>
              <th className="px-3 py-3 text-right">Total</th>
              <th className="px-3 py-3">Endereço</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-agp-border">
            {rows.map((r, i) => {
              const cor = colorMap[r.rota_vuc];
              return (
                <tr key={i} className="hover:bg-agp-card/60 transition">
                  <td
                    className="px-3 py-2 font-semibold"
                    style={cor ? { color: cor } : undefined}
                  >
                    {cor && (
                      <span
                        className="inline-block w-2 h-2 rounded-full mr-2 align-middle"
                        style={{ background: cor }}
                      />
                    )}
                    {r.rota_vuc}
                  </td>
                  <td className="px-3 py-2 font-mono text-agp-muted">{r.seq}</td>
                  <td className="px-3 py-2 font-mono">{r.chegada}</td>
                  <td className="px-3 py-2 text-gray-100">{r.cliente}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.pos}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.pb_ts}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.grandes}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.medias}</td>
                  <td
                    className="px-3 py-2 text-right font-mono font-semibold"
                    style={cor ? { color: cor } : undefined}
                  >
                    {r.total}
                  </td>
                  <td className="px-3 py-2 text-agp-muted">{r.endereco}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
