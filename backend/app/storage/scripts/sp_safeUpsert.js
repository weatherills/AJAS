function sp_safeUpsert(doc) {
    var context = getContext();
    var collection = context.getCollection();
    var response = context.getResponse();
    if (!doc || !doc.id) {
        throw new Error("document id is required");
    }
    var link = collection.getAltLink() + "/docs/" + doc.id;
    var accepted = collection.readDocument(link, function (err, existing) {
        if (err && err.number !== 404) {
            throw err;
        }
        var now = new Date().toISOString();
        if (existing) {
            var incoming = Number(doc.schemaVersion || 0);
            var current = Number(existing.schemaVersion || 0);
            if (incoming && current && incoming < current) {
                throw new Error("stale schemaVersion");
            }
            doc.schemaVersion = current + 1;
            doc.created_at = existing.created_at || now;
            doc.updated_at = now;
            var replaced = collection.replaceDocument(existing._self, doc, function (err2) {
                if (err2) throw err2;
                response.setBody(doc);
            });
            if (!replaced) throw new Error("replace not accepted");
            return;
        }
        doc.schemaVersion = Number(doc.schemaVersion || 0) + 1;
        doc.created_at = doc.created_at || now;
        doc.updated_at = now;
        var created = collection.createDocument(collection.getSelfLink(), doc, function (err3) {
            if (err3) throw err3;
            response.setBody(doc);
        });
        if (!created) throw new Error("create not accepted");
    });
    if (!accepted) throw new Error("read not accepted");
}
