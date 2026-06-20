import { OtimizacaoResposta } from "../api/types";

interface Props {
  resp: OtimizacaoResposta;
}

export default function Warnings({ resp }: Props) {
  return (
    <div className="space-y-3">
      {resp.osrm_indisponivel && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 text-yellow-200 rounded-xl px-4 py-3 text-sm">
          ⚠️ Servidor de roteamento OSRM instável. Distâncias e traçado estão
          em <strong>linha reta aproximada</strong>; os agrupamentos seguem
          corretos.
        </div>
      )}

      {resp.violacoes_janela.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 text-yellow-200 rounded-xl px-4 py-3 text-sm">
          ⚠️{" "}
          <strong>
            {resp.violacoes_janela.length} VUC(s) terminam após 18:00
          </strong>
          .
          <ul className="mt-2 list-disc list-inside text-xs space-y-0.5">
            {resp.violacoes_janela.map((v, i) => (
              <li key={i}>
                <span className="text-agp-blue">{v.vuc}</span> — {v.paradas}{" "}
                paradas, {v.pecas} pç, término {v.termino}
              </li>
            ))}
          </ul>
        </div>
      )}

      {resp.violacoes_km.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-200 rounded-xl px-4 py-3 text-sm">
          🚨{" "}
          <strong>
            {resp.violacoes_km.length} VUC(s) excedem o limite de KM
          </strong>
          .
          <ul className="mt-2 list-disc list-inside text-xs space-y-0.5">
            {resp.violacoes_km.map((v, i) => (
              <li key={i}>
                <span className="text-agp-blue">{v.vuc}</span> — {v.km_real} km
                (limite {v.limite})
              </li>
            ))}
          </ul>
        </div>
      )}

      {resp.enderecos_nao_localizados.length > 0 && (
        <details className="bg-amber-500/10 border border-amber-500/30 text-amber-200 rounded-xl px-4 py-3 text-sm">
          <summary className="cursor-pointer font-semibold">
            ⚠️ {resp.enderecos_nao_localizados.length} endereço(s) não
            localizado(s)
          </summary>
          <ul className="mt-2 list-disc list-inside text-xs space-y-0.5">
            {resp.enderecos_nao_localizados.map((e, i) => (
              <li key={i}>
                <strong className="text-gray-100">{e.cliente}</strong> —{" "}
                {e.endereco} ({e.motivo})
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
