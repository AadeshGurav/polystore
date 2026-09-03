frappe.ui.form.on("Library Book", {
	onload_post_render(frm) {
		show_stored_attributes(frm);
	},

	edit_attributes_btn(frm) {
		edit_attributes(frm);
	},

	refresh(frm) {
		show_stored_attributes(frm);

		if (frm.is_new()) return;

		frm.dashboard.add_comment(
			__("Attributes below live in MongoDB; series and borrowing edges in Neo4j. Only the fields above are SQL columns."),
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

function show_stored_attributes(frm) {
	// Virtual fields are stripped from as_dict(), so the value arrives in __onload.
	const stored = (frm.doc.__onload || {}).polystore_payload;
	if (!frm.doc.attributes_json) {
		frm.doc.attributes_json = stored || "{}";
	}

	frm.refresh_field("attributes_json");
}

function edit_attributes(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Flexible attributes"),
		size: "large",
		fields: [
			{
				fieldname: "help",
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"Any JSON object. These keys are written to MongoDB, not to a SQL column, so they may differ from one book to the next."
				)}</p>`,
			},
			{
				fieldname: "payload",
				fieldtype: "Code",
				label: __("Attributes (JSON)"),
				default: frm.doc.attributes_json || "{}",
			},
		],
		primary_action_label: __("Save to MongoDB"),
		primary_action(values) {
			let parsed;
			try {
				parsed = JSON.parse(values.payload || "{}");
			} catch (error) {
				frappe.msgprint({ title: __("Invalid JSON"), message: String(error), indicator: "red" });
				return;
			}

			if (Array.isArray(parsed) || typeof parsed !== "object") {
				frappe.msgprint({ title: __("Invalid JSON"), message: __("Attributes must be an object."), indicator: "red" });
				return;
			}

			const pretty = JSON.stringify(parsed, null, 2);
			dialog.hide();

			if (frm.is_new()) {
				// Nothing to write to yet — the value rides along with the insert.
				frm.doc.attributes_json = pretty;
				frm.refresh_field("attributes_json");
				frappe.show_alert({ message: __("Attributes will be written when you save the book."), indicator: "blue" });
				return;
			}

			frappe
				.call("polystore.api.catalog.save_attributes", { book: frm.doc.name, payload: pretty })
				.then(() => {
					frm.doc.attributes_json = pretty;
					frm.refresh_field("attributes_json");
					frappe.show_alert({ message: __("Written to MongoDB."), indicator: "green" });
				});
		},
	});

	dialog.show();
}

function show_rows(title, rows, format) {
	const list = (rows || []).map((row) => `<li>${frappe.utils.escape_html(format(row))}</li>`).join("");
	frappe.msgprint({
		title,
		message: list ? `<ul>${list}</ul>` : __("Nothing found in the graph for this record."),
	});
}
