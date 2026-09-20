function trg_setTimestamps() {
    var request = getContext().getRequest();
    var doc = request.getBody();
    var now = new Date().toISOString();
    if (!doc.created_at) {
        doc.created_at = now;
    }
    doc.updated_at = now;
    if (!doc.schemaVersion) {
        doc.schemaVersion = 1;
    }
    request.setBody(doc);
}
