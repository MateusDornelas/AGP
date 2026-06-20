import { useEffect, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Polyline,
  Popup,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { OtimizacaoResposta } from "../api/types";
import { corDoVuc } from "../lib/colors";

// CD Central — Santana de Parnaíba/SP (igual ao backend).
const DEPOT: [number, number] = [-23.4357, -46.9427];

function depotIcon(): L.DivIcon {
  return L.divIcon({
    className: "agp-depot-icon",
    html: `<div style="
      width: 28px; height: 28px;
      border-radius: 6px;
      background: #111;
      border: 2px solid #F5C518;
      display: flex; align-items: center; justify-content: center;
      color: #F5C518; font-weight: bold; font-size: 14px;
      box-shadow: 0 2px 8px rgba(0,0,0,.5);
    ">CD</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function numberedIcon(numero: number, cor: string): L.DivIcon {
  return L.divIcon({
    className: "agp-stop-icon",
    html: `<div style="
      width: 26px; height: 26px;
      border-radius: 50%;
      background: ${cor};
      border: 2px solid white;
      display: flex; align-items: center; justify-content: center;
      color: white; font-weight: bold; font-size: 12px;
      box-shadow: 0 2px 6px rgba(0,0,0,.6);
    ">${numero}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

interface FitBoundsProps {
  pontos: [number, number][];
}

function FitBounds({ pontos }: FitBoundsProps) {
  const map = useMap();
  useEffect(() => {
    if (pontos.length === 0) return;
    const bounds = L.latLngBounds(pontos.map((p) => L.latLng(p[0], p[1])));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
  }, [map, pontos]);
  return null;
}

interface Props {
  resp: OtimizacaoResposta;
}

export default function MapView({ resp }: Props) {
  // Lista de pontos pra auto-fit (depot + todas as paradas)
  const todosPontos = useMemo<[number, number][]>(() => {
    const pts: [number, number][] = [DEPOT];
    for (const v of resp.vucs) {
      for (const p of v.paradas) {
        pts.push([p.lat, p.lon]);
      }
    }
    return pts;
  }, [resp]);

  if (resp.vucs.length === 0) return null;

  return (
    <section>
      <h2 className="text-lg font-semibold mb-3 text-gray-100">
        🗺️ Mapa das Rotas
      </h2>
      <div className="bg-agp-surface border border-agp-border rounded-2xl overflow-hidden">
        <MapContainer
          center={DEPOT}
          zoom={10}
          style={{ height: "520px", width: "100%" }}
          scrollWheelZoom
        >
          {/* Tiles light/clean (CartoDB Positron — fundo cinza-claro com
              ruas em branco, sem cores conflitantes com as linhas dos VUCs). */}
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
            subdomains="abcd"
          />

          {/* Depot */}
          <Marker position={DEPOT} icon={depotIcon()}>
            <Popup>
              <strong>CD Central</strong>
              <br />
              Santana de Parnaíba/SP
            </Popup>
          </Marker>

          {/* Rotas: polilinhas + paradas numeradas por VUC.
              - route_geometry preenchido (lista) → rota REAL pelas ruas (OSRM)
              - route_geometry null (OSRM falhou) → fallback reta
              - route_geometry undefined (preview de edição) → SEM linha
                (evita exibir reta "buguada" enquanto auto-reotimização roda). */}
          {resp.vucs.map((vuc, vucIdx) => {
            const cor = corDoVuc(vucIdx);

            let linha: [number, number][] | null = null;
            if (vuc.route_geometry && vuc.route_geometry.length > 1) {
              linha = vuc.route_geometry;
            } else if (vuc.route_geometry === null) {
              linha = [
                DEPOT,
                ...vuc.paradas.map(
                  (p) => [p.lat, p.lon] as [number, number]
                ),
                DEPOT,
              ];
            }
            // undefined => sem linha; só markers (preview do swap em andamento)

            return (
              <div key={vuc.label}>
                {linha && (
                  <Polyline
                    positions={linha}
                    pathOptions={{
                      color: cor,
                      weight: 4,
                      opacity: 0.85,
                    }}
                  />
                )}
                {vuc.paradas.map((p) => (
                  <Marker
                    key={`${vuc.label}-${p.seq}`}
                    position={[p.lat, p.lon]}
                    icon={numberedIcon(p.seq, cor)}
                  >
                    <Popup>
                      <div style={{ minWidth: 200 }}>
                        <div style={{ fontWeight: 700, color: cor }}>
                          {vuc.label} · Parada {p.seq}
                        </div>
                        <div style={{ margin: "4px 0" }}>{p.cliente}</div>
                        <div style={{ fontSize: 12, color: "#666" }}>
                          {p.endereco}
                        </div>
                        <div style={{ fontSize: 12, marginTop: 4 }}>
                          🕐 Chegada estimada: <strong>{p.chegada}</strong>
                        </div>
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </div>
            );
          })}

          <FitBounds pontos={todosPontos} />
        </MapContainer>
      </div>

      {/* Legenda */}
      <div className="mt-3 flex flex-wrap gap-2">
        {resp.vucs.map((vuc, idx) => (
          <span
            key={vuc.label}
            className="flex items-center gap-1.5 text-xs bg-agp-card border border-agp-border rounded-lg px-2 py-1 text-gray-200"
          >
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ background: corDoVuc(idx) }}
            />
            {vuc.label}
            <span className="text-agp-muted">
              · {vuc.paradas.length} parada(s)
            </span>
          </span>
        ))}
      </div>
    </section>
  );
}
