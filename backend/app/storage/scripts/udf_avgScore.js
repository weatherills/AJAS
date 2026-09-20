function udf_avgScore(scores) {
    if (!scores || !scores.length) {
        return 0;
    }
    var total = 0;
    var count = 0;
    for (var i = 0; i < scores.length; i++) {
        var value = Number(scores[i]);
        if (!isNaN(value)) {
            total += value;
            count += 1;
        }
    }
    return count ? total / count : 0;
}
