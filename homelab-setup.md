# Homelab Setup — Повна документація

> HP Elite Mini 800 G9 · Proxmox VE 9.2 · Arch Linux (ноут)  
> Дата: червень 2026

---

## Зміст

1. [Залізо](#залізо)
2. [BIOS налаштування](#bios-налаштування)
3. [Proxmox встановлення](#proxmox-встановлення)
4. [Диски та сховище](#диски-та-сховище)
5. [Мережа та DNS](#мережа-та-dns)
6. [WireGuard VPN](#wireguard-vpn)
7. [LXC Контейнер (services)](#lxc-контейнер-services)
8. [Docker стек](#docker-стек)
9. [Caddy reverse proxy](#caddy-reverse-proxy)
10. [Vaultwarden](#vaultwarden)
11. [503Work — застосунок](#503work--застосунок)
12. [Cloudflare DDNS](#cloudflare-ddns)
13. [Безпека](#безпека)
14. [Корисні команди](#корисні-команди)

---

## Залізо

| Компонент | Модель |
|---|---|
| Сервер | HP Elite Mini 800 G9 (i5-12500T) |
| RAM | 2×8GB DDR5-4800 SO-DIMM |
| SSD 1 (система) | 256GB M.2 2242 (з адаптером 2242→2280) |
| SSD 2 (дані) | 256GB M.2 2242 (з адаптером 2242→2280) |
| NIC додатковий | HP Flex IO V2 2.5GbE (M74416) |
| Роутер | TP-Link Archer C20 |

**Мережа:**
```
Proxmox:   192.168.0.150
CT services: 192.168.0.151
WireGuard сервер: 10.0.0.1
WireGuard ноут:   10.0.0.2
```

---

## BIOS налаштування

**Вхід:** F10 при старті → HP Computer Setup

### Security
```
Secure Boot: Disabled
(після збереження ввести 4-значний код з екрану)
```

### Advanced → System Options
```
Virtualization Technology (VTx): Enabled
Virtualization Technology for I/O (VTd): Enabled
```

### Advanced → Power Management
```
PCI Express Power Management: Disabled
Runtime Power Management: Disabled
Extended Idle Power States: Disabled
Wake On LAN: Enabled
```

### Advanced → Boot Options
```
Fast Boot: Disabled
USB Storage Boot: Enabled
Boot Order: USB → NVMe → Network
```

### Advanced → Storage Options
```
SATA Emulation: AHCI
```

### MEBx (Intel AMT) — Ctrl+P при старті
```
Змінити пароль з дефолтного 'admin'
Network Setup → DHCP: Enabled
Activate Network Access: Yes
Доступ: http://192.168.0.150:16992
```

---

## Proxmox встановлення

### Запис ISO
```bash
# Завантажити з proxmox.com/en/downloads
sudo dd if=proxmox-ve_9.2-1.iso of=/dev/sdb bs=4M status=progress conv=fsync
```

### Параметри встановлення
```
Filesystem:  ext4
Disk:        /dev/nvme1n1 (системний)
Country:     Ukraine
Timezone:    Europe/Kyiv
Hostname:    pve.home.arpa
IP:          192.168.0.150/24
Gateway:     192.168.0.1
DNS:         192.168.0.1
Pin Network Interface Names: ✓
```

### Після встановлення — виправлення репозиторіїв
```bash
# Вимкнути enterprise репо
echo "# disabled" > /etc/apt/sources.list.d/pve-enterprise.list
echo "# disabled" > /etc/apt/sources.list.d/pve-enterprise.sources
echo "# disabled" > /etc/apt/sources.list.d/ceph.list
echo "# disabled" > /etc/apt/sources.list.d/ceph.sources

# Додати безкоштовний репо
echo "deb http://download.proxmox.com/debian/pve trixie pve-no-subscription" \
  > /etc/apt/sources.list.d/pve-no-subscription.list

apt update && apt upgrade -y
```

### IOMMU (для PCIe passthrough)
```bash
nano /etc/default/grub
# Змінити:
GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"

update-grub

echo "vfio" >> /etc/modules
echo "vfio_iommu_type1" >> /etc/modules
echo "vfio_pci" >> /etc/modules

reboot
```

### SSH keepalive (на ноуті)
```bash
nano ~/.ssh/config
# Додати:
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 10
```

---

## Диски та сховище

### Стан дисків
```
nvme1n1  → системний Proxmox (pve-root, pve-swap, local-lvm)
nvme0n1  → диск даних → /mnt/data
```

### Налаштування диску даних
```bash
# Розмітка
fdisk /dev/nvme0n1
# g → n → Enter → Enter → Enter → w

# Форматування
mkfs.ext4 /dev/nvme0n1p1

# Точка монтування
mkdir -p /mnt/data

# UUID
blkid /dev/nvme0n1p1

# fstab
echo "UUID=89db88d2-1deb-4d89-8949-b2e3d9032999 /mnt/data ext4 defaults 0 2" >> /etc/fstab
systemctl daemon-reload
mount -a
```

### Додавання сховища в Proxmox
```
Datacenter → Storage → Add → Directory
ID:        data
Directory: /mnt/data
Content:   Disk image, Container, ISO, VZDump backup file, Snippets
```

### Структура папок
```
/mnt/data/services/          # = /data всередині CT 100 (mp0)
  caddy/
    config/
    data/
    logs/
  vaultwarden/
  503work/                   # git-репо застосунку (docker-compose, .env, backup.sh)
  backups/                   # дампи БД 503work (= /data/backups у CT)
  logs/                      # логи ETL — etl.log (= /data/logs у CT)
  nextcloud/
    data/
    db/
  immich/
  postgres/
  redis/
```

---

## Мережа та DNS

### Домен
- Реєстратор: Cloudflare Registrar
- Домен: `kod0ri.com`

### DNS записи в Cloudflare
```
A    @          77.47.205.214   Proxied 🟠
A    *          77.47.205.214   DNS only 🔘
A    503work    77.47.205.214   Proxied 🟠
A    vault      77.47.205.214   DNS only 🔘
A    vpn        77.47.205.214   DNS only 🔘
```

> `vpn.kod0ri.com` і `vault.kod0ri.com` — DNS only (без проксі)  
> WireGuard і Caddy самі керують TLS

### Port Forward на роутері (TP-Link Archer C20)
```
UDP 51820 → 192.168.0.150  (WireGuard)
TCP 80    → 192.168.0.151  (Caddy CT)
TCP 443   → 192.168.0.151  (Caddy CT)
```

### Локальні аліаси (на ноуті)
```bash
nano /etc/hosts
# Додати:
10.0.0.1       proxmox.home pve.home
192.168.0.151  services.home
```

```bash
# ~/.ssh/config
Host proxmox
    HostName 10.0.0.1
    User root
    IdentityFile ~/.ssh/id_ed25519
```

---

## WireGuard VPN

### Сервер (Proxmox)

```bash
apt install -y wireguard wireguard-tools
cd /etc/wireguard

# Ключі сервера
wg genkey | tee server_private.key | wg pubkey > server_public.key
# Ключі клієнта
wg genkey | tee client_private.key | wg pubkey > client_public.key
chmod 600 *_private.key
```

`/etc/wireguard/wg0.conf`:
```ini
[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = <SERVER_PRIVATE_KEY>

PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o vmbr0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o vmbr0 -j MASQUERADE

[Peer]
PublicKey = <CLIENT_PUBLIC_KEY>
AllowedIPs = 10.0.0.2/32
```

```bash
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p
systemctl enable wg-quick@wg0
systemctl start wg-quick@wg0
```

### Клієнт (Arch Linux ноут)

```bash
sudo pacman -S wireguard-tools openresolv
```

`/etc/wireguard/wg0.conf`:
```ini
[Interface]
Address = 10.0.0.2/24
PrivateKey = <CLIENT_PRIVATE_KEY>

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = vpn.kod0ri.com:51820
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
```

```bash
# Підняти VPN
sudo wg-quick up wg0

# Вимкнути VPN
sudo wg-quick down wg0
```

### Додавання нових клієнтів
```bash
cd /etc/wireguard
wg genkey | tee phone_private.key | wg pubkey > phone_public.key

# Додати в wg0.conf:
[Peer]
PublicKey = <PHONE_PUBLIC_KEY>
AllowedIPs = 10.0.0.3/32

systemctl restart wg-quick@wg0
```

---

## LXC Контейнер (services)

### Створення CT

```
CT ID:      100
Hostname:   services
Template:   ubuntu-24.04-standard
Disk:       32GB (local-lvm)
CPU:        2 cores
RAM:        2048MB
Swap:       512MB
IP:         192.168.0.151/24
Gateway:    192.168.0.1
DNS:        1.1.1.1
Unprivileged: ✓
```

### Конфіг CT (`/etc/pve/lxc/100.conf`)
```
arch: amd64
cores: 2
features: keyctl=1,nesting=1
hostname: services
memory: 2048
nameserver: 1.1.1.1
net0: name=eth0,bridge=vmbr0,firewall=1,gw=192.168.0.1,ip=192.168.0.151/24,type=veth
ostype: ubuntu
rootfs: local-lvm:vm-100-disk-0,size=32G
searchdomain: local
swap: 512
unprivileged: 1
mp0: /mnt/data/services,mp=/data
```

> `features: keyctl=1,nesting=1` — обов'язково для Docker  
> `mp0` — bind mount диску даних

### Команди керування CT
```bash
pct start 100      # запустити
pct stop 100       # зупинити
pct enter 100      # увійти в CT
pct status 100     # статус
```

### Встановлення Docker в CT
```bash
apt update && apt upgrade -y
apt install -y curl wget git nano htop
curl -fsSL https://get.docker.com | sh
```

---

## Docker стек

### Структура файлів
```
/opt/docker/
  docker-compose.yml
  Caddyfile
  .env
```

### `.env`
```
CF_API_TOKEN=<CLOUDFLARE_API_TOKEN>
```

### `docker-compose.yml`
```yaml
services:

  caddy:
    image: ghcr.io/caddybuilds/caddy-cloudflare:latest
    container_name: caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - /data/caddy/data:/data/caddy
      - /data/caddy/config:/config
      - /data/caddy/logs:/data/logs
      - /opt/docker/Caddyfile:/etc/caddy/Caddyfile
    environment:
      - CF_API_TOKEN=${CF_API_TOKEN}

  vaultwarden:
    image: vaultwarden/server:latest
    container_name: vaultwarden
    restart: unless-stopped
    volumes:
      - /data/vaultwarden:/data
    environment:
      - WEBSOCKET_ENABLED=true
      - SIGNUPS_ALLOWED=false

  cloudflare-ddns:
    image: favonia/cloudflare-ddns:latest
    container_name: cloudflare-ddns
    restart: unless-stopped
    network_mode: host
    environment:
      - CF_API_TOKEN=${CF_API_TOKEN}
      # ВСІ записи з таблиці DNS — явні записи (503work, vault) НЕ оновлюються
      # через wildcard, тому мають бути перелічені окремо
      - DOMAINS=kod0ri.com,*.kod0ri.com,503work.kod0ri.com,vault.kod0ri.com,vpn.kod0ri.com
      # proxied лише там, де в таблиці 🟠 (favonia підтримує вирази per-domain)
      - PROXIED=is(kod0ri.com) || is(503work.kod0ri.com)
      - UPDATE_CRON=@every 5m

  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_SCHEDULE=0 0 4 * * *

networks:
  default:
    name: homelab
```

### Команди Docker
```bash
cd /opt/docker

docker compose up -d           # запустити всі сервіси
docker compose down            # зупинити всі
docker compose restart caddy   # перезапустити конкретний
docker compose logs -f caddy   # логи в реальному часі
docker compose ps              # статус контейнерів
docker compose pull            # оновити образи
```

---

## Caddy reverse proxy

### `Caddyfile`
```
{
    email admin@kod0ri.com
    acme_dns cloudflare {env.CF_API_TOKEN}
}

vault.kod0ri.com {
    log {
        output file /data/logs/access.log
        format json
    }
    reverse_proxy vaultwarden:80
}

503work.kod0ri.com {
    encode gzip zstd
    reverse_proxy labor_market_frontend:80
}
```

### Додавання нового сервісу
```
новий-сервіс.kod0ri.com {
    reverse_proxy container_name:port
}
```

Після зміни Caddyfile:
```bash
docker compose restart caddy
```

---

## Vaultwarden

**URL:** https://vault.kod0ri.com  
**Self-hosted Bitwarden-сумісний менеджер паролів**

### Підключення клієнта
```
Bitwarden додаток → Settings → Self-hosted environment
Server URL: https://vault.kod0ri.com
```

### Міграція з Bitwarden
```
Bitwarden → Settings → Export Vault → JSON
Vaultwarden → Tools → Import Data → Bitwarden (json)
```

### Важливо
```yaml
# Після реєстрації вимкнути нові реєстрації
environment:
  - SIGNUPS_ALLOWED=false
```

---

## 503Work — застосунок

**URL:** https://503work.kod0ri.com

Аналітика українського IT-ринку праці: ETL (work.ua → Groq LLM → PostgreSQL) +
FastAPI + React-дашборд. Окремий Docker-стек у мережі `homelab`, проксі через Caddy.

> Канонічна інструкція деплою — `DEPLOY.md` у репозиторії.
> Тут — лише специфіка homelab (шляхи `/data/...`, мережа `homelab`, Caddy).
> Зміни процедури деплою вноси спочатку в `DEPLOY.md`.

### Розміщення
```
/data/503work/        # git-репозиторій (= /mnt/data/services/503work)
  docker-compose.yml
  docker-compose.prod.yml   # prod-override (підключається через COMPOSE_FILE)
  .env                # секрети, НЕ в git
  backup.sh
/data/backups/        # дампи БД
/data/logs/           # логи ETL
```

### Перший деплой
```bash
cd /data
git clone https://github.com/kod0ri/labor_market_Information_and_analytical_system.git 503work
cd 503work
git checkout v1.0.0                  # деплоїмо тег, не гілку
cp .env.example .env && nano .env    # заповнити секрети (нижче)

# підключити prod-override — далі ВСІ docker compose команди (up, run, cron)
# підхоплюють його автоматично з .env
echo "COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml" >> .env

# мережа homelab має існувати (інфра-стек /opt/docker піднятий)
docker network ls | grep homelab || (cd /opt/docker && docker compose up -d)

docker compose up -d --build         # db + api + frontend
docker compose run --rm etl_worker   # перший збір даних (30-90 хв)
```

### .env — обов'язкові prod-змінні
```
DB_USER / DB_PASSWORD / DB_NAME      # сильний пароль
GROQ_API_KEY                         # console.groq.com
JWT_SECRET                           # openssl rand -hex 32
ADMIN_USERNAME / ADMIN_PASSWORD      # НЕ admin/admin
CORS_ORIGINS=https://503work.kod0ri.com
```

### Сервіси
```
db          postgres:16-alpine   :5432 (127.0.0.1)
api         FastAPI / uvicorn     :8000 (127.0.0.1)
frontend    nginx + React         :80   (через Caddy → homelab)
pgadmin     профіль tools         — зі стеком не стартує
etl_worker  профіль manual        — лише cron / вручну
```

### Оновлення (новий реліз)
```bash
cd /data/503work
./backup.sh                                  # бекап ПЕРЕД оновленням
git fetch --tags && git checkout vX.Y.Z
docker compose up -d --build                 # перебудує лише змінене
docker compose ps                            # smoke-перевірка
```

### Rollback
```bash
cd /data/503work
git checkout <попередній-тег>
docker compose up -d --build
# при пошкодженні БД — відновити з /data/backups (нижче)
```

### ETL за розкладом (cron)
Модель `llama-4-scout-17b` (free tier): RPD=1K, **TPD=500K** ← вузьке місце.
Один прогін ≈ 200 запитів / 170K токенів (100 вакансій + 100 резюме).
Денна стеля ≈ 590 записів. Стабільно — **1/день**; для backlog — **2/день**.

```cron
# стабільний режим — 1 прогін/день о 05:00
0 5 * * * /usr/bin/flock -n /tmp/etl.lock bash -c 'cd /data/503work && docker compose run --rm -T etl_worker' >> /data/logs/etl.log 2>&1

# режим backlog — ТИМЧАСОВО 2/день (05:00 і 17:00), ~340K/500K TPD; повернути 1/день після добору даних
# 0 5,17 * * * /usr/bin/flock -n /tmp/etl.lock bash -c 'cd /data/503work && docker compose run --rm -T etl_worker' >> /data/logs/etl.log 2>&1
```

> `-T` (без TTY) і `flock` (без накладань прогонів) — обов'язкові для cron.

### Бекап БД (cron)
`/data/503work/backup.sh` — `pg_dump` через контейнер, gzip, тримає 14 останніх.

```cron
0 3 * * * /data/503work/backup.sh >> /data/backups/backup.log 2>&1
```

Відновлення:
```bash
gunzip -c /data/backups/503work_<TS>.sql.gz | \
  docker compose -f /data/503work/docker-compose.yml exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

### Авто-рестарт
- `restart: always` на всіх сервісах — падіння контейнера → Docker підніме.
- `systemctl enable docker` у CT — ребут CT → стек встане.
- `pct set 100 --onboot 1` на хості Proxmox — ребут хоста → CT стартує.

### Захист
- Адмінка `/api/admin/*` — за JWT; `ADMIN_PASSWORD` і `JWT_SECRET` згенеровані, не дефолтні.
- Брутфорс логіну — Cloudflare WAF rate-limit на `/api/auth/login` (5 req/хв/IP).
- Cloudflare SSL/TLS: **Full (strict)** — Caddy має валідний Let's Encrypt сертифікат.
- Порт БД у проді не публікується взагалі (`docker-compose.prod.yml`), API прибитий до `127.0.0.1`; назовні лише 80/443 через Caddy.

---

## Cloudflare DDNS

Автоматично оновлює DNS записи при зміні IP провайдера.

Один контейнер `cloudflare-ddns` оновлює **всі** записи з таблиці DNS
(apex, wildcard, `503work`, `vault`, `vpn`). Явні записи треба перелічувати
в `DOMAINS` окремо — оновлення wildcard їх не зачіпає. Прапорець proxied
задається per-domain виразом `PROXIED=is(...) || is(...)` відповідно до таблиці.

> Додаєш новий явний A-запис у Cloudflare → додай його і в `DOMAINS`,
> інакше при зміні IP він залишиться зі старою адресою.

Перевірка:
```bash
docker compose logs cloudflare-ddns
```

---

## Безпека

### Стан портів
```
Назовні відкрито:
  UDP 51820  → WireGuard (єдина точка входу для адмінки)
  TCP 80     → Caddy (redirect to HTTPS)
  TCP 443    → Caddy (публічні сервіси)

Закрито назовні:
  TCP 22     → SSH (тільки через VPN 10.0.0.0/24)
  TCP 8006   → Proxmox (тільки через VPN)
  Все інше   → DROP
```

### SSH захист (`/etc/ssh/sshd_config`)
```
# БЕЗ ListenAddress 10.0.0.1: sshd стартує раніше за wg0 і не зможе
# забіндитись → локаут (рятує лише фізична консоль). Доступ "тільки через
# VPN" і так забезпечує файрвол (port 22 лише з 10.0.0.0/24).
PermitRootLogin prohibit-password
PasswordAuthentication no
KexAlgorithms sntrup761x25519-sha512@openssh.com,curve25519-sha256,diffie-hellman-group16-sha512
Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
HostKeyAlgorithms ssh-ed25519,rsa-sha2-512,rsa-sha2-256
```

### Proxmox Firewall (`/etc/pve/firewall/cluster.fw`)
```ini
[OPTIONS]
enable: 1
policy_in: DROP
policy_out: ACCEPT

[RULES]
IN ACCEPT -p udp --dport 51820
IN ACCEPT -p tcp --dport 80
IN ACCEPT -p tcp --dport 443
IN ACCEPT -p tcp --dport 22 -source 10.0.0.0/24
IN ACCEPT -p tcp --dport 8006 -source 10.0.0.0/24
IN ACCEPT -source 192.168.0.0/24
```

### Fail2ban на Proxmox

`/etc/fail2ban/jail.d/proxmox.conf`:
```ini
[DEFAULT]
bantime  = 86400
findtime = 600
maxretry = 3

[sshd]
enabled = true
port    = ssh

[proxmox]
enabled = true
port    = https,http,8006
filter  = proxmox
logpath = /var/log/daemon.log
```

`/etc/fail2ban/filter.d/proxmox.conf`:
```ini
[Definition]
failregex = pvedaemon\[.*\]: authentication failure; rhost=<HOST>
ignoreregex =
```

### Fail2ban в CT

`/etc/fail2ban/jail.d/homelab.conf`:
```ini
[DEFAULT]
bantime  = 86400
findtime = 600
maxretry = 5

[sshd]
enabled  = true
maxretry = 3
```

---

## Корисні команди

### Proxmox
```bash
# Статус VM/CT
pct list
qm list

# Firewall
pve-firewall status
pve-firewall restart

# Версія
pveversion

# Логи
journalctl -f
```

### WireGuard
```bash
# Статус
wg show

# Перезапустити
systemctl restart wg-quick@wg0

# Ноут — підняти/вимкнути
sudo wg-quick up wg0
sudo wg-quick down wg0
```

### Docker
```bash
# Всі контейнери
docker ps -a

# Логи
docker compose logs -f

# Оновити і перезапустити
docker compose pull && docker compose up -d

# Очистити невикористані образи
docker system prune -f
```

### Fail2ban
```bash
# Статус всіх jail
fail2ban-client status

# Статус конкретного jail
fail2ban-client status sshd

# Розблокувати IP
fail2ban-client set sshd unbanip <IP>
```

### Tmux
```bash
tmux new -s main      # нова сесія
tmux attach -t main   # приєднатись
tmux ls               # список сесій
# Ctrl+B D             # відключитись (сесія живе)
```

---

## Що далі

```
□ OPNsense VM (firewall + IDS/IPS Suricata)
□ Nextcloud (файли + sync Obsidian)
□ Immich (фото)
□ AdGuard Home (локальний DNS + блокування реклами)
□ Uptime Kuma (моніторинг сервісів)
□ Proxmox автобекап CT
□ NAS (Jonsbo N2 + TrueNAS) — майбутнє
□ MikroTik CRS310 свіч — майбутнє
□ C2 lab VM для диплому
```
