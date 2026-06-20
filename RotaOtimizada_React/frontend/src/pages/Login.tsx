import { FormEvent, useState } from "react";
import { login, setSession } from "../api/client";

interface Props {
  onSuccess: (usuario: string) => void;
}

export default function Login({ onSuccess }: Props) {
  const [usuario, setUsuario] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      const r = await login(usuario, senha);
      setSession(r.token, r.usuario);
      onSuccess(r.usuario);
    } catch (err: any) {
      setErro(err.message || "Erro inesperado");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-agp-bg px-4">
      <div className="w-full max-w-sm bg-agp-surface border border-agp-border rounded-2xl shadow-xl p-8">
        <div className="flex justify-center mb-6">
          <img src="/AGPpng.png" alt="AGP" className="h-20 object-contain" />
        </div>
        <h1 className="text-2xl font-semibold text-center text-gray-100 mb-1">
          Otimizador Logístico
        </h1>
        <p className="text-sm text-agp-muted text-center mb-6">
          Acesso restrito — informe suas credenciais
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-agp-muted mb-1">
              👤 Usuário
            </label>
            <input
              type="text"
              className="w-full bg-agp-card border border-agp-border rounded-xl px-4 py-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-agp-blue"
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-agp-muted mb-1">
              🔒 Senha
            </label>
            <input
              type="password"
              className="w-full bg-agp-card border border-agp-border rounded-xl px-4 py-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-agp-blue"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
            />
          </div>
          {erro && (
            <div className="text-sm rounded-lg px-3 py-2 border bg-red-500/10 text-red-300 border-red-500/30">
              {erro}
            </div>
          )}
          <button
            type="submit"
            disabled={carregando}
            className="w-full bg-agp-blue text-agp-black font-bold py-3 rounded-xl hover:opacity-90 disabled:opacity-50 transition"
          >
            {carregando ? "Validando…" : "Entrar"}
          </button>
        </form>

        <p className="text-xs text-agp-muted text-center mt-6">AGP Glass</p>
      </div>
    </div>
  );
}
