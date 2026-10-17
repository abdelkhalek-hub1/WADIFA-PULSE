"""
Wadifa Pulse - Module de Sécurité & Validation
Protection contre les emails temporaires (tempmail), génération OTP & validation cryptographique
"""

import re
import secrets
from datetime import datetime, timedelta

# Liste exhaustive des domaines de messagerie temporaire / jetable (tempmail, throwaway, yopmail, etc.)
DISPOSABLE_DOMAINS = {
    # Temp-Mail & dérivés
    "tempmail.com", "temp-mail.org", "temp-mail.io", "tempmail.net", "tempmail.de",
    "tempmailaddress.com", "temp-mail.ru", "tempmailo.com", "tempail.com",
    # 10 Minute Mail
    "10minutemail.com", "10minutemail.net", "10minutemail.org", "10minmail.com",
    "minuteinbox.com", "minutemail.com", "10minutemailbox.com",
    # Guerrilla Mail
    "guerrillamail.com", "guerrillamail.net", "guerrillamail.org", "guerrillamail.biz",
    "guerrillamail.de", "guerrillamailblock.com", "grr.la", "sharklasers.com", "pokemail.net",
    "spam4.me", "bccto.me",
    # Yopmail & alias
    "yopmail.com", "yopmail.fr", "yopmail.net", "cool.fr.nf", "courriel.qc.ca",
    "jetable.fr.nf", "nospam.ze.tc", "nomail.xl.cx", "mega.zik.dj", "speed.1s.fr",
    # Mailinator & dérivés
    "mailinator.com", "mailinator.net", "mailinator2.com", "suremail.info", "binkmail.com",
    "safetymail.info", "sendspamhere.com", "trashymail.com",
    # Trashmail
    "trashmail.com", "trashmail.net", "trashmail.me", "trashmail.io", "trashmail.ws",
    # Mohmal & arab disposable
    "mohmal.com", "mohmal.im", "mohmal.in", "mohmal.tech",
    # Autres acteurs majeurs de messagerie temporaire
    "throwawaymail.com", "dispostable.com", "getairmail.com", "fakeinbox.com",
    "crazymailing.com", "burnermail.io", "mytemp.email", "generator.email",
    "tempinbox.com", "inboxkitten.com", "getnada.com", "dropmail.me", "internxt.com",
    "emailondeck.com", "zillamail.com", "nada.ltd", "maildrop.cc", "luxusmail.org",
    "harakirimail.com", "chacuo.net", "0-mail.com", "disposablemail.com", "clipmail.eu",
    "byom.de", "mailnull.com", "spambox.us", "inboxalias.com", "e4ward.com",
    "gishpuppy.com", "kasmail.com", "mailexpire.com", "mailcatch.com", "tempemail.co",
    "fakemailgenerator.com", "armyspy.com", "cuvox.de", "dayrep.com", "fleckens.hu",
    "gustr.com", "jourrapide.com", "rhyta.com", "superrito.com", "teleworm.us",
    "mytempemail.com", "mytempemail.net", "mytempemail.org", "inboxclean.com",
    "fakemail.net", "fakemail.org", "fakeemail.com", "burnermail.com", "trash-mail.com",
    "crazymail.com", "throwaway.email", "discard.email", "discardmail.com",
    "tempmailgen.com", "emailfake.com", "crazymailing.net", "maildrop.cf",
    "guerrillamail.info", "getairmail.net", "sharklasers.net"
}

# Mots-clés suspects dans le nom de domaine
SUSPICIOUS_DOMAIN_KEYWORDS = [
    "tempmail", "temp-mail", "disposable", "fakeinbox", "throwaway", "10minute",
    "trashmail", "trash-mail", "yopmail", "guerrilla", "mailinator", "burnermail",
    "fakemail", "discardmail", "minutemail"
]

def is_disposable_email(email: str) -> tuple[bool, str]:
    """
    Vérifie si une adresse email provient d'un service temporaire / jetable.
    Renvoie (is_disposable, message_explicatif).
    """
    clean_email = (email or "").strip().lower()
    if not clean_email or "@" not in clean_email:
        return True, "Adresse email invalide."

    parts = clean_email.split("@")
    if len(parts) != 2:
        return True, "Format d'adresse email invalide."

    domain = parts[1].strip()

    # 1. Vérification par domaine exact
    if domain in DISPOSABLE_DOMAINS:
        return True, "Les adresses email temporaires ou jetables ne sont pas autorisées. Veuillez utiliser une adresse email valide (Gmail, Outlook, Yahoo, etc.)."

    # 2. Vérification par sous-domaines (ex: *.mailinator.com)
    for disp in DISPOSABLE_DOMAINS:
        if domain.endswith("." + disp):
            return True, "Les adresses email temporaires ou jetables ne sont pas autorisées. Veuillez utiliser une adresse email valide."

    # 3. Vérification par heuristique de mots-clés suspects
    domain_name_only = domain.split(".")[0]
    for kw in SUSPICIOUS_DOMAIN_KEYWORDS:
        if kw in domain_name_only:
            return True, "Les services d'adresses email temporaires ne sont pas autorisés sur Wadifa Pulse."

    return False, ""

def generate_otp_code() -> str:
    """Génère un code OTP cryptographique aléatoire de 6 chiffres."""
    return f"{secrets.randbelow(900000) + 100000}"

def get_otp_expiry(minutes: int = 15) -> datetime:
    """Calcule la date d'expiration de l'OTP (par défaut 15 minutes)."""
    return datetime.utcnow() + timedelta(minutes=minutes)
