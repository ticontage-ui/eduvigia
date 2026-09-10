import React from "react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || "Erro inesperado" };
  }

  componentDidCatch(error, info) {
    console.error("EduVigIA UI error", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <main className="fatalError">
        <img src="/eduvigia-brand.png" alt="EduVigIA" />
        <h1>Não foi possível abrir esta tela</h1>
        <p>{this.state.message}</p>
        <button type="button" onClick={() => window.location.reload()}>
          Recarregar sistema
        </button>
      </main>
    );
  }
}
