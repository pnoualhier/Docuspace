# DocuSpace — Sauvegardes & Restauration

## 1. Procédure de Sauvegarde Automatisée

DocuSpace fournit le script autonome `scripts/backup/backup.sh`.
Il réalise :
1. Un dump binaire compressé de la base PostgreSQL (`pg_dump -F c`).
2. Une archive compressée du stockage d'objets MinIO.
3. Une copie sécurisée de la configuration `.env`.
4. La génération d'un fichier de vérification d'intégrité `SHA256SUMS`.
5. La purge automatique des sauvegardes antérieures à 14 jours.

### Exécution Manuelle
```bash
chmod +x scripts/backup/backup.sh
./scripts/backup/backup.sh
```

### Automatisation via Cron (Tous les jours à 2h00 du matin)
```bash
sudo crontab -e
# Ajouter :
0 2 * * * /opt/docuspace/scripts/backup/backup.sh >> /var/log/docuspace_backup.log 2>&1
```

---

## 2. Procédure de Restauration

En cas de reprise après sinistre :
```bash
chmod +x scripts/restore/restore.sh
./scripts/restore/restore.sh /var/backups/docuspace/<TIMESTAMP_DE_SAUVEGARDE>
```

Le script vérifie automatiquement les sommes de contrôle SHA256, restaure la base PostgreSQL puis les volumes MinIO.
