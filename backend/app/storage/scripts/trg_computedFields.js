function trg_computedFields() {
    var request = getContext().getRequest();
    var doc = request.getBody();
    var now = new Date().toISOString();
    if (!doc.created_at) {
        doc.created_at = now;
    }
    if (!doc.createdAt) {
        doc.createdAt = doc.created_at;
    }
    doc.updated_at = now;
    doc.updatedAt = now;
    if (Array.isArray(doc.status_history) && doc.status_history.length) {
        var last = doc.status_history[doc.status_history.length - 1];
        doc.status_rollup = last && (last.status || last.event_type);
    }
    if (Array.isArray(doc.items)) {
        doc.item_count = doc.items.length;
    }
    request.setBody(doc);
}
