function udf_contains(haystack, needle) {
    if (!needle) {
        return true;
    }
    if (haystack === null || haystack === undefined) {
        return false;
    }
    return String(haystack).toLowerCase().indexOf(String(needle).toLowerCase()) !== -1;
}
