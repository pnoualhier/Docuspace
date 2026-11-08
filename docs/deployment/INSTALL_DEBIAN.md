# DocuSpace — Guide d'Installation sur Serveur Debian 12 (Bookworm)

Ce guide détaille la mise en service complète de **DocuSpace** sur un serveur dédié ou VPS Debian 12.

## 1. Prérequis Système

- Système d'exploitation : **Debian 12 (Bookworm)**
- Processeur : 2 vCPU minimum (4 recommandés pour ClamAV et conversions LibreOffice)
- Mémoire RAM : 4 Go minimum (8 Go recommandés)
- Espace Disque : 50 Go SSD ou plus

---

## 2. Installation de Docker & Docker Compose

Exécutez les commandes suivantes avec les droits `sudo` :

```bash
# 1. Mise à jour des paquets et dépendances
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl gnupg ca-certificates lsb-release

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

# 2. Préparer les variables d'environnement
cp .env.example .env

# Générer des secrets forts :
sed -i "s/replace_with_strong_random_db_password/$(openssl rand -hex 24)/g" .env
sed -i "s/replace_with_strong_minio_secret_key/$(openssl rand -hex 24)/g" .env
sed -i "s/replace_with_strong_redis_password/$(openssl rand -hex 24)/g" .env
sed -i "s/generate_with_openssl_rand_hex_32_change_me/$(openssl rand -hex 32)/g" .env

# 3. Lancer les conteneurs avec Docker Compose
docker compose up -d --build

# 4. Vérifier l'état de santé de tous les services
docker compose ps
```

---

## 4. Initialisation de la Base de Données & Migrations

```bash
# Exécution automatique des migrations Alembic
docker compose exec backend alembic upgrade head
```

L'application est immédiatement accessible sur `http://<IP_DU_SERVEUR>` ou via votre nom de domaine configuré sur Nginx.
