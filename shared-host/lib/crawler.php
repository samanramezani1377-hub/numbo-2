<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';
require_once __DIR__ . '/extract.php';

function numbo_allowed_tlds(): array
{
    $cfg = numbo_config();
    $tlds = $cfg['allowed_tlds'] ?? ['.ir'];
    return array_values(array_filter(array_map('strval', $tlds)));
}

function numbo_tld_ok(string $host): bool
{
    $tlds = numbo_allowed_tlds();
    if (!$tlds) {
        return true;
    }
    $host = strtolower($host);
    foreach ($tlds as $t) {
        $t = strtolower($t);
        if ($t !== '' && str_ends_with($host, $t)) {
            return true;
        }
    }
    return false;
}

function numbo_enqueue_seeds(): int
{
    $raw = numbo_meta('seeds', '');
    $n = 0;
    $db = numbo_db();
    $ins = $db->prepare('INSERT OR IGNORE INTO queue(url, domain, depth, status) VALUES(?,?,0,"pending")');
    foreach (preg_split('/\R/', (string)$raw) as $line) {
        $line = trim($line);
        if ($line === '' || str_starts_with($line, '#')) {
            continue;
        }
        if (!preg_match('#^https?://#i', $line)) {
            $line = 'https://' . $line;
        }
        $host = strtolower((string)parse_url($line, PHP_URL_HOST));
        $host = preg_replace('/^www\./', '', $host) ?? $host;
        if ($host === '' || !numbo_tld_ok($host)) {
            continue;
        }
        $ins->execute([$line, $host]);
        $n += $ins->rowCount();
    }
    return $n;
}

function numbo_fetch(string $url): array
{
    if (!function_exists('curl_init')) {
        throw new RuntimeException('php-curl is required');
    }
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 4,
        CURLOPT_TIMEOUT => 18,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_USERAGENT => 'NumboSharedBot/1.0',
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_SSL_VERIFYHOST => false,
        CURLOPT_ENCODING => '',
    ]);
    $body = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err = curl_error($ch);
    curl_close($ch);
    if ($body === false) {
        throw new RuntimeException($err ?: 'fetch failed');
    }
    if ($code >= 400) {
        throw new RuntimeException('HTTP ' . $code);
    }
    return ['html' => (string)$body, 'code' => $code];
}

function numbo_save_contact(array $row): void
{
    $st = numbo_db()->prepare('INSERT OR IGNORE INTO contacts
        (source_url, domain, title, phones, emails, business_name, category, city, socials, technologies, crawled_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)');
    $st->execute([
        $row['source_url'],
        $row['domain'],
        $row['title'],
        $row['phones'],
        $row['emails'],
        $row['business_name'],
        $row['category'],
        $row['city'],
        $row['socials'],
        $row['technologies'],
        $row['crawled_at'],
    ]);
}

function numbo_run_batch(int $limit = 6): array
{
    if (numbo_meta('running', '0') !== '1') {
        return ['ok' => false, 'msg' => 'stopped', 'done' => 0];
    }
    numbo_enqueue_seeds();
    $db = numbo_db();
    $sel = $db->prepare("SELECT id, url, domain, depth FROM queue WHERE status='pending' ORDER BY id ASC LIMIT ?");
    $sel->execute([$limit]);
    $jobs = $sel->fetchAll(PDO::FETCH_ASSOC);
    $done = 0;
    $errors = [];
    $mark = $db->prepare('UPDATE queue SET status=? WHERE id=?');
    $insQ = $db->prepare('INSERT OR IGNORE INTO queue(url, domain, depth, status) VALUES(?,?,?,"pending")');

    foreach ($jobs as $job) {
        if (numbo_meta('running', '0') !== '1') {
            break;
        }
        $mark->execute(['working', $job['id']]);
        try {
            $res = numbo_fetch($job['url']);
            $html = $res['html'];
            $text = html_entity_decode(strip_tags($html), ENT_QUOTES | ENT_HTML5, 'UTF-8');
            $phones = numbo_extract_phones($text);
            $emails = numbo_extract_emails($text);
            $techs = numbo_detect_tech($html, $job['url']);
            $title = '';
            if (preg_match('#<title[^>]*>(.*?)</title>#is', $html, $tm)) {
                $title = trim(html_entity_decode(strip_tags($tm[1])));
            }
            $domain = $job['domain'];
            if ($phones || $emails || $techs) {
                numbo_save_contact([
                    'source_url' => $job['url'],
                    'domain' => $domain,
                    'title' => $title,
                    'phones' => implode(',', $phones),
                    'emails' => implode(',', $emails),
                    'business_name' => $title !== '' ? explode('|', explode('-', $title)[0])[0] : $domain,
                    'category' => numbo_detect_category($text),
                    'city' => numbo_detect_city($text),
                    'socials' => json_encode(numbo_extract_socials($html), JSON_UNESCAPED_UNICODE),
                    'technologies' => implode('; ', $techs),
                    'crawled_at' => gmdate('c'),
                ]);
            }
            $depth = (int)$job['depth'];
            if ($depth < 2 && preg_match_all('/href=["\']([^"\']+)["\']/i', $html, $hm)) {
                foreach (array_slice($hm[1], 0, 30) as $href) {
                    $full = numbo_abs_url($job['url'], $href);
                    if (!$full) {
                        continue;
                    }
                    $h = strtolower((string)parse_url($full, PHP_URL_HOST));
                    $h = preg_replace('/^www\./', '', $h) ?? $h;
                    if ($h !== $domain || !numbo_tld_ok($h)) {
                        continue;
                    }
                    $insQ->execute([$full, $h, $depth + 1]);
                }
            }
            $mark->execute(['done', $job['id']]);
            $done++;
            usleep(800000);
        } catch (Throwable $e) {
            $mark->execute(['error', $job['id']]);
            $errors[] = $job['url'] . ': ' . $e->getMessage();
        }
    }
    return ['ok' => true, 'done' => $done, 'errors' => $errors, 'left' => (int)$db->query("SELECT COUNT(*) FROM queue WHERE status='pending'")->fetchColumn()];
}

function numbo_abs_url(string $base, string $href): ?string
{
    $href = trim($href);
    if ($href === '' || str_starts_with($href, '#') || str_starts_with($href, 'javascript:') || str_starts_with($href, 'mailto:')) {
        return null;
    }
    if (preg_match('#^https?://#i', $href)) {
        return $href;
    }
    $p = parse_url($base);
    if (!$p || empty($p['scheme']) || empty($p['host'])) {
        return null;
    }
    $origin = $p['scheme'] . '://' . $p['host'] . (isset($p['port']) ? ':' . $p['port'] : '');
    if (str_starts_with($href, '//')) {
        return $p['scheme'] . ':' . $href;
    }
    if (str_starts_with($href, '/')) {
        return $origin . $href;
    }
    $path = $p['path'] ?? '/';
    $dir = preg_replace('#/[^/]*$#', '/', $path) ?: '/';
    return $origin . $dir . $href;
}
