function trg_enqueueHint() {
    var request = getContext().getRequest();
    var doc = request.getBody ? request.getBody() : null;
    var response = getContext().getResponse();
    var body = response.getBody ? response.getBody() : doc;
    if (!body) {
        return;
    }
    var hints = {
        submit_requests: "auto-apply-submits",
        auto_apply_attempts: "auto-apply-requests",
        match_runs: "match-compute",
        source_fetch_runs: "crawl-runs",
        resume_parse_events: "resume-parse"
    };
    var queue = hints[body._container] || null;
    if (queue) {
        body._enqueue = { queue: queue, documentId: body.id };
        if (response.setBody) {
            response.setBody(body);
        }
    }
}
