/**
 * Paleta compartilhada de cores por VUC.
 * Usada no MapView (linhas/marcadores), DataTable (coluna Rota/VUC) e
 * ResumeCards (borda dos cards). Mantém a consistência visual entre
 * todas as visualizações da otimização.
 */

export const CORES_VUC = [
  "#EF4444", // red-500
  "#3B82F6", // blue-500
  "#10B981", // emerald-500
  "#F59E0B", // amber-500
  "#A855F7", // purple-500
  "#EC4899", // pink-500
  "#06B6D4", // cyan-500
  "#84CC16", // lime-500
];

export function corDoVuc(idx: number): string {
  return CORES_VUC[idx % CORES_VUC.length];
}

/** Constrói um lookup label → cor a partir da ordem dos VUCs. */
export function montarColorMap(labels: string[]): Record<string, string> {
  const m: Record<string, string> = {};
  labels.forEach((l, i) => {
    m[l] = corDoVuc(i);
  });
  return m;
}
