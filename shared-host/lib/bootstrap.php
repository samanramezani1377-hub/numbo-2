<?php
declare(strict_types=1);

session_start();

define('NUMBO_ROOT', dirname(__DIR__));
define('NUMBO_DATA', NUMBO_ROOT . '/data');
define('NUMBO_CONFIG', NUMBO_ROOT . '/config.php');
define('NUMBO_DB', NUMBO_DATA . '/numbo.sqlite');

if (!is_dir(NUMBO_DATA)) {
    mkdir(NUMBO_DATA, 0755, true);
}

function numbo_config(): array
{
    if (!is_file(NUMBO_CONFIG)) {
        return [];
    }
    $cfg = include NUMBO_CONFIG;
    return is_array($cfg) ? $cfg : [];
}

function numbo_save_config(array $cfg): void
{
    $export = var_export($cfg, true);
    $php = "<?php\nreturn {$export};\n";
    file_put_contents(NUMBO_CONFIG, $php, LOCK_EX);
}

function numbo_db(): PDO
{
    static $pdo = null;
    if ($pdo) {
        return $pdo;
    }
    if (!extension_loaded('pdo_sqlite')) {
        throw new RuntimeException('pdo_sqlite is required');
    }
    $pdo = new PDO('sqlite:' . NUMBO_DB);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->exec('PRAGMA journal_mode=WAL');
    $pdo->exec("CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_url TEXT,
        domain TEXT,
        title TEXT,
        phones TEXT,
        emails TEXT,
        business_name TEXT,
        category TEXT,
        city TEXT,
        socials TEXT,
        technologies TEXT,
        crawled_at TEXT,
        UNIQUE(source_url, phones)
    )");
    $pdo->exec("CREATE TABLE IF NOT EXISTS queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        domain TEXT,
        depth INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending'
    )");
    $pdo->exec("CREATE TABLE IF NOT EXISTS meta (
        k TEXT PRIMARY KEY,
        v TEXT
    )");
    return $pdo;
}

function numbo_meta(string $k, ?string $default = null): ?string
{
    $st = numbo_db()->prepare('SELECT v FROM meta WHERE k = ?');
    $st->execute([$k]);
    $v = $st->fetchColumn();
    return $v === false ? $default : (string)$v;
}

function numbo_set_meta(string $k, string $v): void
{
    $st = numbo_db()->prepare('INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v');
    $st->execute([$k, $v]);
}

function numbo_logged_in(): bool
{
    return !empty($_SESSION['numbo_ok']);
}

function numbo_require_login(): void
{
    if (!numbo_logged_in()) {
        header('Location: index.php?view=login');
        exit;
    }
}
