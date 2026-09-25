<?php
declare(strict_types=1);

function numbo_normalize_phone(string $phone): string
{
    $digits = preg_replace('/\D+/', '', $phone) ?? '';
    if (str_starts_with($digits, '98') && strlen($digits) >= 12) {
        $digits = '0' . substr($digits, 2);
    }
    if (str_starts_with($digits, '9') && strlen($digits) === 10) {
        $digits = '0' . $digits;
    }
    return $digits;
}

function numbo_extract_phones(string $text): array
{
    $found = [];
    if (preg_match_all('/(?:\+98|98|0)?9(?:0[1-5]|1[0-9]|2[0-2]|3[0-9]|9[0-9])\d{7}/u', $text, $m)) {
        foreach ($m[0] as $p) {
            $n = numbo_normalize_phone($p);
            if (strlen($n) === 11 && str_starts_with($n, '09')) {
                $found[$n] = $n;
            }
        }
    }
    return array_values($found);
}

function numbo_extract_emails(string $text): array
{
    if (!preg_match_all('/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/', $text, $m)) {
        return [];
    }
    $out = [];
    foreach ($m[0] as $e) {
        $out[strtolower($e)] = strtolower($e);
    }
    return array_values($out);
}

function numbo_detect_city(string $text): string
{
    $map = [
        'تهران' => ['تهران', 'tehran'],
        'اصفهان' => ['اصفهان', 'isfahan', 'esfahan'],
        'مشهد' => ['مشهد', 'mashhad'],
        'شیراز' => ['شیراز', 'shiraz'],
        'تبریز' => ['تبریز', 'tabriz'],
        'کرج' => ['کرج', 'karaj'],
        'اهواز' => ['اهواز', 'ahvaz'],
        'قم' => ['قم', 'qom'],
        'رشت' => ['رشت', 'rasht'],
        'یزد' => ['یزد', 'yazd'],
    ];
    $lower = mb_strtolower($text);
    foreach ($map as $city => $kws) {
        foreach ($kws as $kw) {
            if (mb_stripos($lower, $kw) !== false) {
                return $city;
            }
        }
    }
    return '';
}

function numbo_detect_category(string $text): string
{
    $map = [
        'فروشگاه' => ['فروشگاه', 'shop', 'store'],
        'رستوران' => ['رستوران', 'restaurant', 'کافه'],
        'پزشکی' => ['پزشک', 'کلینیک', 'clinic'],
        'املاک' => ['املاک', 'real estate'],
        'آموزش' => ['آموزش', 'آموزشگاه'],
        'فناوری' => ['نرم‌افزار', 'software'],
    ];
    $lower = mb_strtolower($text);
    foreach ($map as $cat => $kws) {
        foreach ($kws as $kw) {
            if (mb_stripos($lower, $kw) !== false) {
                return $cat;
            }
        }
    }
    return 'عمومی';
}

function numbo_detect_tech(string $html, string $url = ''): array
{
    $blob = strtolower($html . ' ' . $url);
    $rules = [
        'WordPress' => ['wp-content', 'wp-includes', 'wordpress'],
        'WooCommerce' => ['woocommerce', 'wc-add-to-cart', 'wc-block'],
        'Joomla' => ['joomla', '/components/com_'],
        'Drupal' => ['drupal', '/sites/default/files'],
        'Shopify' => ['cdn.shopify.com', 'myshopify.com'],
        'Laravel' => ['laravel'],
        'Next.js' => ['_next/static', '__next_data__'],
        'Cloudflare' => ['cloudflare'],
    ];
    $out = [];
    foreach ($rules as $name => $needles) {
        $hits = 0;
        foreach ($needles as $n) {
            if (str_contains($blob, $n)) {
                $hits++;
            }
        }
        if ($hits > 0) {
            $conf = min(1, round($hits / max(count($needles) * 0.6, 1), 2));
            if ($conf < 0.35) {
                $conf = 0.5;
            }
            $out[] = $name . '(' . $conf . ')';
        }
    }
    return $out;
}

function numbo_extract_socials(string $html): array
{
    $socials = [];
    if (preg_match_all('/href=["\']([^"\']+)["\']/i', $html, $m)) {
        foreach ($m[1] as $href) {
            $l = strtolower($href);
            if (str_contains($l, 'instagram.com')) {
                $socials['instagram'] = $href;
            } elseif (str_contains($l, 't.me') || str_contains($l, 'telegram')) {
                $socials['telegram'] = $href;
            } elseif (str_contains($l, 'linkedin.com')) {
                $socials['linkedin'] = $href;
            }
        }
    }
    return $socials;
}
