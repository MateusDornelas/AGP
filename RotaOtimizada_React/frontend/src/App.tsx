import Dashboard from "./pages/Dashboard";

// LOGIN EM STAND BY — a tela e o endpoint /api/auth/login continuam
// no código (Login.tsx + routers/auth.py) mas estão desligados do fluxo.
// Para reativar: voltar pra versão antiga deste arquivo (git history) e
// re-adicionar `Depends(require_token)` em optimize.py / reoptimize.py.
export default function App() {
  return <Dashboard usuario="Operador" onLogout={() => { /* noop */ }} />;
}
