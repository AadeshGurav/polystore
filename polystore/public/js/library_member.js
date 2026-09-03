frappe.ui.form.on("Library Member", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Recommendations"), () => {
			frappe.call("polystore.api.catalog.recommendations", { member: frm.doc.name }).then((r) => {
				const rows = r.message || [];
				frappe.msgprint({
					title: __("Suggested for {0}", [frm.doc.member_name]),
					message: rows.length
						? `<ul>${rows
								.map(
									(row) =>
										`<li>${frappe.utils.escape_html(row.title)} — ${row.shared_readers} shared reader(s)</li>`
								)
								.join("")}</ul>`
						: __("No suggestions yet — this member shares no books with anyone."),
				});
			});
		}, __("Graph"));

		frm.add_custom_button(__("Connection to another member"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Shortest path through shared books"),
				fields: [{ fieldname: "other", fieldtype: "Link", options: "Library Member", label: __("Member"), reqd: 1 }],
				primary_action_label: __("Trace"),
				primary_action(values) {
					frappe
						.call("polystore.api.catalog.connection", {
							member_a: frm.doc.name,
							member_b: values.other,
						})
						.then((r) => {
							const rows = r.message || [];
							dialog.hide();
							frappe.msgprint({
								title: __("Connection"),
								message: rows.length
									? rows
											.map(
												(row) =>
													`<p>${frappe.utils.escape_html(row.hops.join(" → "))} <span class="text-muted">(${row.distance} hops)</span></p>`
											)
											.join("")
									: __("No path between these members."),
							});
						});
				},
			});
			dialog.show();
		}, __("Graph"));
	},
});
