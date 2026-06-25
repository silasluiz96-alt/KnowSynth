"""
Módulo de envio de e-mail do KnowSynth via SendGrid.

Responsabilidade única: enviar o relatório de sessão formatado para o e-mail
informado pelo aluno ao encerrar a sessão.

Uso:
    from utils.email_sender import enviar_relatorio

    ok, msg = enviar_relatorio(
        destinatario="aluno@email.com",
        aluno_nome="João",
        relatorio={"resumo_sessao": "...", "pontos_fracos": [...], ...},
    )
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


def enviar_relatorio(
    destinatario: str,
    aluno_nome: str,
    relatorio: dict,
) -> tuple[bool, str]:
    """
    Envia o relatório de sessão por e-mail via SendGrid.

    Parâmetros:
        destinatario — e-mail do aluno
        aluno_nome   — nome usado na sessão (para personalizar o assunto)
        relatorio    — dict retornado por PerformanceAnalyst.generate_report()

    Retorna:
        (True, "E-mail enviado com sucesso!")  se enviou
        (False, "mensagem de erro amigável")   se falhou
    """
    api_key    = os.getenv("SENDGRID_API_KEY")
    remetente  = os.getenv("EMAIL_REMETENTE")

    if not api_key:
        log.warning("[email_sender] SENDGRID_API_KEY ausente — e-mail não enviado.")
        return False, "Serviço de e-mail não configurado."

    if not remetente:
        log.warning("[email_sender] EMAIL_REMETENTE ausente — e-mail não enviado.")
        return False, "Remetente não configurado."

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        resumo      = relatorio.get("resumo_sessao", "Sem resumo disponível.")
        pontos      = relatorio.get("pontos_fracos", [])
        recomend    = relatorio.get("recomendacoes", [])
        preview     = relatorio.get("preview_v2", "")

        pontos_html = "".join(
            f"<li style='margin-bottom:6px'>{p}</li>" for p in pontos
        ) if pontos else "<li>Nenhum ponto fraco identificado — ótimo desempenho!</li>"

        recomend_html = "".join(
            f"<li style='margin-bottom:6px'>{r}</li>" for r in recomend
        ) if recomend else "<li>Continue estudando com regularidade!</li>"

        html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#0e1117;color:#e0e0e0;padding:32px;margin:0">
  <div style="max-width:600px;margin:0 auto">

    <div style="text-align:center;margin-bottom:32px">
      <h1 style="color:#00d4ff;font-size:2rem;margin:0">KnowSynth</h1>
      <p style="color:#888;margin:4px 0 0">Relatório da sua sessão de estudos</p>
    </div>

    <div style="background:#1a1d27;border-radius:12px;padding:24px;margin-bottom:20px;border-left:4px solid #00d4ff">
      <h2 style="color:#00d4ff;margin:0 0 12px">Olá, {aluno_nome}! 👋</h2>
      <p style="line-height:1.7;margin:0">{resumo}</p>
    </div>

    <div style="background:#1a1d27;border-radius:12px;padding:24px;margin-bottom:20px;border-left:4px solid #ff4b6e">
      <h3 style="color:#ff4b6e;margin:0 0 12px">🎯 Pontos que merecem atenção</h3>
      <ul style="margin:0;padding-left:20px;line-height:1.7">
        {pontos_html}
      </ul>
    </div>

    <div style="background:#1a1d27;border-radius:12px;padding:24px;margin-bottom:20px;border-left:4px solid #00ff88">
      <h3 style="color:#00ff88;margin:0 0 12px">📋 Recomendações para a próxima sessão</h3>
      <ul style="margin:0;padding-left:20px;line-height:1.7">
        {recomend_html}
      </ul>
    </div>

    <div style="background:#1a1d27;border-radius:12px;padding:16px;margin-bottom:32px;text-align:center">
      <p style="color:#888;margin:0;font-size:.85rem">{preview}</p>
    </div>

    <div style="text-align:center;border-top:1px solid #333;padding-top:20px">
      <p style="color:#555;font-size:.78rem;margin:0">
        KnowSynth — Assistente de estudos para o ENEM com IA<br>
        Este e-mail foi enviado porque você solicitou o relatório ao encerrar sua sessão.
      </p>
    </div>

  </div>
</body>
</html>
"""

        mensagem = Mail(
            from_email=remetente,
            to_emails=destinatario,
            subject=f"📊 Seu relatório de estudos — {aluno_nome} | KnowSynth",
            html_content=html,
        )

        sg = SendGridAPIClient(api_key)
        response = sg.send(mensagem)

        if response.status_code in (200, 202):
            log.info("[email_sender] E-mail enviado para %s (status %d)", destinatario, response.status_code)
            return True, "E-mail enviado com sucesso! Verifique sua caixa de entrada."
        else:
            log.warning("[email_sender] SendGrid retornou status %d", response.status_code)
            return False, f"Erro ao enviar e-mail (código {response.status_code})."

    except Exception as exc:
        log.warning("[email_sender] Falha ao enviar e-mail: %s", exc)
        return False, "Não foi possível enviar o e-mail. Tente novamente mais tarde."
