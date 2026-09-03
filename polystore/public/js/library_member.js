frappe.ui.form.on("Library Member", {
	onload_post_render(frm) {
		paint_graph_fields(frm);
	},

	edit_attributes_btn(frm) {
		edit_profile(frm);
	},

	manage_connections_btn(frm) {
		manage_connections(frm);
	},

	refresh(frm) {
		paint_graph_fields(frm);

		if (frm.is_new()) return;

		frm.dashboard.add_comment(
			__("Contact and membership fields are SQL columns. The profile below is a MongoDB document. Connections exist only as Neo4j edges."),
			"blue",
			true
		);

		frm.add_custom_button(__("Book recommendations"), () => {
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

		frm.add_custom_button(__("Path to another member"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Shortest path through shared books"),
				fields: [{ fieldname: "other", fieldtype: "Link", options: "Library Member", label: __("Member"), reqd: 1 }],
				primary_action_label: __("Trace"),
				primary_action(values) {
					frappe
						.call("polystore.api.catalog.connection", { member_a: frm.doc.name, member_b: values.other })
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

function paint_graph_fields(frm) {
	const onload = frm.doc.__onload || {};

	if (!frm.doc.attributes_json) {
		frm.doc.attributes_json = onload.polystore_payload || "{}";
	}

	const knows = onload.polystore_connections || [];
	const suggestions = onload.polystore_suggestions || [];

	frm.doc.known_members = knows.length
		? knows.map((row) => `${row.member_name} (${row.membership_type || "Standard"})`).join("\n")
		: __("No connections yet.");

	frm.doc.suggested_members = suggestions.length
		? suggestions
				.map((row) => `${row.member_name} — ${row.mutuals} mutual via ${(row.through || []).join(", ")}`)
				.join("\n")
		: __("Nothing two hops out.");

	frm.refresh_field("attributes_json");
	frm.refresh_field("known_members");
	frm.refresh_field("suggested_members");
}

function edit_profile(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Reader profile"),
		size: "large",
		fields: [
			{
				fieldname: "help",
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"Any JSON object — favourite genres, reading goals, notes. Written to MongoDB, not to a SQL column."
				)}</p>`,
			},
			{ fieldname: "payload", fieldtype: "Code", label: __("Profile (JSON)"), default: frm.doc.attributes_json || "{}" },
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
				frappe.msgprint({ title: __("Invalid JSON"), message: __("The profile must be an object."), indicator: "red" });
				return;
			}

			const pretty = JSON.stringify(parsed, null, 2);
			dialog.hide();

			if (frm.is_new()) {
				frm.doc.attributes_json = pretty;
				frm.refresh_field("attributes_json");
				frappe.show_alert({ message: __("Profile will be written when you save the member."), indicator: "blue" });
				return;
			}

			frappe.call("polystore.api.catalog.save_member_profile", { member: frm.doc.name, payload: pretty }).then(() => {
				frm.doc.attributes_json = pretty;
				frm.refresh_field("attributes_json");
				frappe.show_alert({ message: __("Written to MongoDB."), indicator: "green" });
			});
		},
	});

	dialog.show();
}

function manage_connections(frm) {
	if (frm.is_new()) {
		frappe.msgprint(__("Save the member first — a graph edge needs both nodes to exist."));
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Connections for {0}", [frm.doc.member_name]),
		size: "large",
		fields: [
			{ fieldname: "current", fieldtype: "HTML" },
			{ fieldname: "other", fieldtype: "Link", options: "Library Member", label: __("Connect to") },
		],
		primary_action_label: __("Add connection"),
		primary_action(values) {
			if (!values.other) return;

			frappe
				.call("polystore.api.catalog.add_member_connection", { member: frm.doc.name, other: values.other })
				.then((r) => {
					dialog.set_value("other", "");
					render(r.message);
				});
		},
	});

	const render = (data) => {
		const rows = (data && data.connections) || [];
		const suggestions = (data && data.suggestions) || [];

		const list = rows.length
			? `<ul class="list-unstyled">${rows
					.map(
						(row) =>
							`<li style="margin-bottom:4px">${frappe.utils.escape_html(row.member_name)}
							<button class="btn btn-xs btn-default ps-drop" data-name="${frappe.utils.escape_html(row.name)}">${__("remove")}</button></li>`
					)
					.join("")}</ul>`
			: `<p class="text-muted">${__("No connections yet.")}</p>`;

		const fof = suggestions.length
			? `<p class="text-muted small">${__("Two hops out")}: ${suggestions
					.map((row) => `${frappe.utils.escape_html(row.member_name)} (${row.mutuals})`)
					.join(", ")}</p>`
			: "";

		dialog.fields_dict.current.$wrapper.html(`<h6>${__("KNOWS edges in Neo4j")}</h6>${list}${fof}`);
		dialog.fields_dict.current.$wrapper.find(".ps-drop").on("click", function () {
			frappe
				.call("polystore.api.catalog.remove_member_connection", {
					member: frm.doc.name,
					other: $(this).data("name"),
				})
				.then((r) => render(r.message));
		});

		frm.doc.__onload = frm.doc.__onload || {};
		frm.doc.__onload.polystore_connections = rows;
		frm.doc.__onload.polystore_suggestions = suggestions;
		paint_graph_fields(frm);
	};

	frappe.call("polystore.api.catalog.member_connections", { member: frm.doc.name }).then((r) => {
		render(r.message);
		dialog.show();
	});
}
