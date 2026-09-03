frappe.ui.form.on("Library Book", {
	onload_post_render(frm) {
		show_stored_attributes(frm);
	},

	refresh(frm) {
		if (frm.is_new()) return;

		show_stored_attributes(frm);

		frm.dashboard.add_comment(
			__("Attributes below are stored in MongoDB; series and borrowing edges in Neo4j. Only the fields above live in SQL."),
			"blue",
			true
		);

		frm.add_custom_button(__("Readers also borrowed"), () => {
			frappe.call("polystore.api.catalog.also_borrowed", { book: frm.doc.name }).then((r) => {
				show_rows(__("Readers also borrowed"), r.message, (row) => `${row.title} — ${row.times} time(s)`);
			});
		}, __("Graph"));

		frm.add_custom_button(__("Series chain"), () => {
			frappe.call("polystore.api.catalog.series_chain", { book: frm.doc.name }).then((r) => {
				show_rows(__("Series chain"), r.message, (row) => `${row.distance} hop(s) back: ${row.title}`);
			});
		}, __("Graph"));

		frm.add_custom_button(__("Raw MongoDB document"), () => {
			frappe.call("polystore.api.catalog.book_attributes", { book: frm.doc.name }).then((r) => {
				frappe.msgprint({
					title: __("MongoDB document"),
					message: `<pre style="font-size:11px">${frappe.utils.escape_html(
						JSON.stringify(r.message || {}, null, 2)
					)}</pre>`,
					wide: true,
				});
			});
		}, __("Graph"));
	},
});

function show_rows(title, rows, format) {
	const list = (rows || []).map((row) => `<li>${frappe.utils.escape_html(format(row))}</li>`).join("");
	frappe.msgprint({
		title,
		message: list ? `<ul>${list}</ul>` : __("Nothing found in the graph for this record."),
	});
}


function show_stored_attributes(frm) {
	const payload = frm.doc.__onload && frm.doc.__onload.polystore_payload;
	if (payload === undefined || payload === null) return;
	if (frm.doc.attributes_json) return;

	frm.doc.attributes_json = payload;
	frm.refresh_field("attributes_json");
}
