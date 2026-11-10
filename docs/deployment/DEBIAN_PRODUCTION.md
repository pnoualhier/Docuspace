# Guide de Déploiement en Production & Durcissement — Debian 12 Bookworm

Ce document constitue le manuel officiel d'exploitation et de durcissement de **DocuSpace** pour un environnement de production sur serveur Debian 12 (Bookworm).

---

## 1. Architecture Réseau et Ségrégation des Ports

Pour garantir la sécurité multi-tenant, aucun port interne de service ne doit être exposé directement sur l'interface publique (`0.0.0.0`).
Seul le reverse proxy **Nginx** écoute sur les ports web publics.

| Service | Port Interne | Exposition Publique | Rôle & Sécurité |
|---|---|---|---|
| **Nginx** | 80, 443 | **OUI** (Public) | Terminaison SSL/TLS, Rate Limiting, WAF |
| **Frontend** | 3000 | **NON** (Réseau Docker) | Application React 19 SPA |
| **Backend API** | 8000 | **NON** (Réseau Docker) | FastAPI, validation JWT, isolation tenant |
| **PostgreSQL 16** | 5432 | **NON** (Réseau Docker) | Base de données RLS étanche |
| **MinIO S3** | 9000, 9001 | **NON** (Réseau Docker) | Stockage d'objets HMAC pré-signé |
| **ClamAV** | 3310 | **NON** (Réseau Docker) | Antivirus Fail-Closed |
| **Redis** | 6379 | **NON** (Réseau Docker) | Cache & verrous avec mot de passe fort |

---

## 2. Durcissement du Système d'Exploitation (Hardening)

### A. Pare-feu UFW (Uncomplicated Firewall)
```bash
sudo apt update && sudo apt install -y ufw

# Règles par défaut strictes
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Autoriser SSH (idéalement sur port personnalisé)
sudo ufw allow 22/tcp

# Autoriser uniquement le trafic Web
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Activer le pare-feu
sudo ufw enable
sudo ufw status verbose
```

### B. Protection Anti-Bruteforce avec Fail2ban
```bash
sudo apt install -y fail2ban
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo systemctl enable --now fail2ban
```

---

## 3. Certificat SSL / TLS Let's Encrypt

Obtention d'un certificat gratuit avec renouvellement automatique :
```bash
sudo apt install -y certbot python3-certbot-nginx

# Obtenir et installer le certificat
sudo certbot --nginx -d votre-domaine.fr -d api.votre-domaine.fr

# Tester le renouvellement automatique
sudo certbot renew --dry-run
```

---

## 4. Sauvegardes Automatisées & Chiffrement

Le script `/opt/docuspace/scripts/backup/backup.sh` sauvegarde :
1. La base de données PostgreSQL (`pg_dump` compressé).
2. Les fichiers et objets stockés dans MinIO S3 (`tar.gz`).
3. La somme de contrôle cryptographique SHA-256 (`sha256sum`) de chaque fichier.
4. Purge automatique des sauvegardes de plus de 14 jours.

Pour planifier l'exécution chaque nuit à 02h00 :
```bash
sudo crontab -e
# Ajouter la ligne :
0 2 * * * /opt/docuspace/scripts/backup/backup.sh >> /var/log/docuspace_backup.log 2>&1
```

---

## 5. Plan de Reprise d'Activité (Disaster Recovery)

En cas d'incident matériel ou logiciel, la restauration est exécutée via :
```bash
sudo /opt/docuspace/scripts/restore/restore.sh /var/backups/docuspace/20261110_020000
```
Le script valide au préalable les sommes SHA-256 de chaque archive avant d'appliquer les restaurations.

---

## 6. Surveillance & Santé du Cluster

```bash
# Vérification globale de tous les conteneurs
docker compose ps

# Consultation des métriques de santé de l'API
curl http://localhost/api/v1/health

# Inspection des journaux en direct
docker compose logs -f --tail=100 backend
```
