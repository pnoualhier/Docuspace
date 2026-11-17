# DocuSpace — Guide d'Installation sur Serveur Debian 12 (Bookworm)

Ce guide détaille la mise en service complète de **DocuSpace** sur un serveur dédié ou VPS Debian 12.

## 1. Prérequis Système

- Système d'exploitation : **Debian 12 (Bookworm)**
- Processeur : 2 vCPU minimum (4 recommandés pour ClamAV)
- Mémoire RAM : 4 Go minimum (8 Go recommandés)
- Espace Disque : 50 Go SSD ou plus

---

## 2. Installation de Docker & Docker Compose

Exécutez les commandes suivantes avec les droits `sudo` :

```bash
# 1. Mise à jour des paquets et dépendances
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl gnupg ca-certificates lsb-release python3

# 2. Ajout de la clé GPG officielle Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 3. Ajout du dépôt Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Installation du moteur Docker et Compose
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Démarrage et activation du service
sudo systemctl enable --now docker
```

---

## 3. Déploiement de DocuSpace

```bash
# 1. Cloner ou transférer le dépôt dans /opt/docuspace
sudo mkdir -p /opt/docuspace
cd /opt/docuspace

# 2. Générer le fichier .env sécurisé à la racine (permissions 600)
# Optionnel : passer le chemin cible et votre URL de domaine en arguments
chmod +x scripts/init/generate_env.sh
./scripts/init/generate_env.sh .env https://votre-domaine.fr

# 3. Lancer les conteneurs avec Docker Compose
docker compose up -d --build

# 4. Vérifier l'état de santé de tous les services
docker compose ps
```

---

## 4. Initialisation de la Base de Données & Migrations

```bash
# Exécution des migrations Alembic (schéma complet, RLS et plans)
docker compose exec backend alembic upgrade head
```

L'application est immédiatement accessible via Nginx sur `http://<IP_DU_SERVEUR>` ou via votre nom de domaine HTTPS configuré.
Aucun port interne (PostgreSQL 5432, Redis 6379, MinIO 9000/9001, ClamAV 3310, Backend 8000, Frontend 3000) n'est exposé publiquement.
