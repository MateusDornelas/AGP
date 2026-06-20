export interface ParadaRota {
  seq: number;
  cliente: string;
  lat: number;
  lon: number;
  endereco: string;
  chegada: string;
}

export interface VucResumo {
  label: string;
  paradas: ParadaRota[];
  /** Polilinha decodificada (lista [lat, lon]) da rota real pelas ruas
   * — vinda do OSRM. Null/undefined quando OSRM falhou (front cai pra reta). */
  route_geometry?: [number, number][] | null;
}

export interface StatsVuc {
  km: number;
  tempo_min: number;
  tempo_label: string;
  pecas: number;
  racks: string;
  custo: number;
  clientes: string[];
}

export interface LinhaTabela {
  rota_vuc: string;
  seq: number;
  chegada: string;
  cliente: string;
  pos: number;
  pb_ts: number;
  grandes: number;
  medias: number;
  total: number;
  endereco: string;
  lat: number;
  lon: number;
}

export interface ViolacaoJanela {
  vuc: string;
  paradas: number;
  pecas: number;
  termino: string;
}

export interface ViolacaoKm {
  vuc: string;
  paradas: number;
  pecas: number;
  km_real: number;
  limite: number;
}

export interface EnderecoNaoLocalizado {
  cliente: string;
  rota: string;
  endereco: string;
  motivo: string;
}

export interface OtimizacaoResposta {
  modo_efetivo: string;
  vucs: VucResumo[];
  stats: Record<string, StatsVuc>;
  table: LinhaTabela[];
  violacoes_janela: ViolacaoJanela[];
  violacoes_km: ViolacaoKm[];
  enderecos_nao_localizados: EnderecoNaoLocalizado[];
  osrm_indisponivel: boolean;
  aviso_fallback: string | null;
}

// Payload do drag-and-drop → /api/reoptimize
export interface ClienteEntrada {
  nome: string;
  endereco: string;
  lat: number;
  lon: number;
  pos: number;
  pb_ts: number;
  pecas_g: number;
  pecas_m: number;
  total: number;
}

export interface VucEntrada {
  label: string;
  clientes: ClienteEntrada[];
}

export interface ReoptimizePayload {
  vucs: VucEntrada[];
}

// Chat com Claude (Anthropic)
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatPayload {
  messages: ChatMessage[];
  route_context: string;
}

export interface ChatResposta {
  resposta: string;
}
