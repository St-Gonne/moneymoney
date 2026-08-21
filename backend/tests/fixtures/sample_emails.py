"""
Synthetic MIME / RFC 822 Forwarded Email Generators for Gate 1 & Gate 2 Testing
"""
import io
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Optional, List, Tuple


def build_forwarded_email(
    forwarder_email: str = "alex.taylor@example.com",
    original_from: str = "Zerodha Contracts <contracts@zerodha.com>",
    subject: str = "Fwd: Contract Note for Trade Date 14-08-2026",
    body_text: Optional[str] = None,
    attachments: Optional[List[Tuple[str, bytes, str]]] = None, # (filename, bytes, mime_subtype)
    inject_malformed_headers: bool = False,
    message_id: str = "<msg-20260814-12345@mail.gmail.com>",
    date_str: str = "Fri, 14 Aug 2026 10:30:00 +0530",
) -> bytes:
    """
    Builds a realistic RFC 822 MIME multipart message representing a Gmail forwarded email.
    """
    if default_body := body_text is None:
        body_text = (
            f"---------- Forwarded message ---------\n"
            f"From: {original_from}\n"
            f"Date: {date_str}\n"
            f"Subject: Contract Note Cum Tax Invoice\n"
            f"To: <{forwarder_email}>\n\n"
            f"Dear Client,\n\nPlease find attached your contract note for recent trades.\n"
        )

    msg = MIMEMultipart()
    if not inject_malformed_headers:
        msg["From"] = forwarder_email
        msg["To"] = forwarder_email
        msg["Subject"] = subject
        msg["Date"] = date_str
        msg["Message-ID"] = message_id
        msg["X-Forwarded-For"] = forwarder_email

    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    if attachments:
        for filename, file_bytes, subtype in attachments:
            part = MIMEApplication(file_bytes, _subtype=subtype)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)

    return msg.as_bytes()


def create_zerodha_mime(
    forwarder: str = "alex.taylor@example.com",
    pdf_bytes: bytes = b"%PDF-1.7 mock zerodha contract note",
    csv_bytes: Optional[bytes] = None,
) -> bytes:
    """Zerodha Contract Note Forwarded Email"""
    atts = [("CN_ZR1102_20260814.pdf", pdf_bytes, "pdf")]
    if csv_bytes:
        atts.append(("tradebook_ZR1102.csv", csv_bytes, "csv"))
    return build_forwarded_email(
        forwarder_email=forwarder,
        original_from="Zerodha Broking Ltd <contracts@zerodha.com>",
        subject="Fwd: Zerodha Contract Note - 14-Aug-2026",
        attachments=atts,
    )


def create_hdfc_mime(
    forwarder: str = "robert.taylor@example.com",
    pdf_bytes: bytes = b"%PDF-1.6 mock hdfc sec contract note",
) -> bytes:
    """HDFC Securities Contract Note Forwarded Email"""
    return build_forwarded_email(
        forwarder_email=forwarder,
        original_from="HDFC Securities <customercare@hdfcsec.com>",
        subject="Fwd: HDFC Sec Electronic Contract Note",
        attachments=[("HDFC_ECN_20260814.pdf", pdf_bytes, "pdf")],
    )


def create_cams_cas_mime(
    forwarder: str = "alex.taylor@example.com",
    pdf_bytes: bytes = b"%PDF-1.4 mock cams consolidated account statement",
) -> bytes:
    """CAMS e-CAS Forwarded Email"""
    return build_forwarded_email(
        forwarder_email=forwarder,
        original_from="CAMS Online <donotreply@camsonline.com>",
        subject="Fwd: Consolidated Account Statement (CAS) - July 2026",
        attachments=[("CAMS_CAS_July2026.pdf", pdf_bytes, "pdf")],
    )


def create_kfintech_cas_mime(
    forwarder: str = "alex.taylor@example.com",
    pdf_bytes: bytes = b"%PDF-1.4 mock kfintech consolidated statement",
) -> bytes:
    """KFintech e-CAS Forwarded Email"""
    return build_forwarded_email(
        forwarder_email=forwarder,
        original_from="KFintech Mutual Fund Services <cas@kfintech.com>",
        subject="Fwd: KFintech e-CAS Statement",
        attachments=[("KFIN_CAS_2026.pdf", pdf_bytes, "pdf")],
    )


def create_schwab_mime(
    forwarder: str = "alex.taylor@example.com",
    csv_bytes: bytes = b"Date,Action,Symbol,Description,Quantity,Price,Fees & Comm,Amount\n05/18/2023,Buy,NVDA,NVIDIA CORP,150,62.40,0.00,-9360.00",
) -> bytes:
    """Charles Schwab US Activity Forwarded Email"""
    return build_forwarded_email(
        forwarder_email=forwarder,
        original_from="Charles Schwab & Co <donotreply@schwab.com>",
        subject="Fwd: Charles Schwab Statement & Activity Export",
        attachments=[("Schwab_Activity_2026.csv", csv_bytes, "csv")],
    )


def create_spoofed_mime(
    forwarder: str = "alex.taylor@example.com",
    fake_domain_from: str = "Zerodha Support <scam@zerodh4.com>",
    pdf_bytes: bytes = b"%PDF-1.7 malicious attachment",
) -> bytes:
    """Email with spoofed broker domain for security testing"""
    return build_forwarded_email(
        forwarder_email=forwarder,
        original_from=fake_domain_from,
        subject="Fwd: Fake Zerodha Contract Note",
        attachments=[("Fake_CN.pdf", pdf_bytes, "pdf")],
    )


def create_unauthorized_forwarder_mime(
    unauthorized_email: str = "attacker@external-domain.com",
    pdf_bytes: bytes = b"%PDF-1.7 untrusted statement",
) -> bytes:
    """Email from unauthorized non-family forwarder"""
    return build_forwarded_email(
        forwarder_email=unauthorized_email,
        original_from="Zerodha Broking Ltd <contracts@zerodha.com>",
        subject="Fwd: Leaked Contract Note",
        attachments=[("Contract_Note.pdf", pdf_bytes, "pdf")],
    )
