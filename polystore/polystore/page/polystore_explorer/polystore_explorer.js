frappe.pages["polystore-explorer"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Store Explorer",
		single_column: true,
	});

	const explorer = new PolystoreExplorer(page);
	page.set_primary_action("Refresh", () => explorer.refresh(), "refresh");
	explorer.refresh();
};

class PolystoreExplorer {
	constructor(page) {
		this.page = page;
		this.book = null;
		this.$body = $(`
			<div class="ps-explorer">
				<div class="ps-status row"></div>
				<div class="ps-record"></div>
				<div class="ps-member-record"></div>
				<div class="row">
					<div class="col-md-6 ps-search"></div>
					<div class="col-md-6 ps-graph"></div>
				</div>
			</div>
		`).appendTo(page.main);

		this.inject_styles();
		this.build_record_panel();
		this.build_member_panel();
		this.build_search_panel();
		this.build_graph_panel();
	}

	inject_styles() {
		if (document.getElementById("ps-explorer-styles")) return;
		$(`<style id="ps-explorer-styles">
			.ps-explorer { padding-bottom: 40px; }
			.ps-explorer .ps-panel { border: 1px solid var(--border-color); border-radius: var(--border-radius-md);
				background: var(--card-bg); padding: 15px; margin-bottom: 15px; }
			.ps-explorer .ps-panel h5 { margin: 0 0 4px; font-size: var(--text-md); }
			.ps-explorer .ps-hint { color: var(--text-muted); font-size: var(--text-sm); margin-bottom: 12px; }
			.ps-explorer pre.ps-json { background: var(--fg-color); border: 1px solid var(--border-color);
				border-radius: var(--border-radius); padding: 10px; font-size: 11px; max-height: 260px; overflow: auto; margin: 0; }
			.ps-explorer .ps-engine { font-size: var(--text-sm); font-weight: 600; margin-bottom: 6px; display: flex;
				justify-content: space-between; align-items: center; }
			.ps-explorer .ps-kv { font-size: var(--text-sm); margin-bottom: 3px; }
			.ps-explorer .ps-kv span { color: var(--text-muted); display: inline-block; min-width: 92px; }
			.ps-explorer .ps-empty { color: var(--text-muted); font-size: var(--text-sm); font-style: italic; }
			.ps-explorer .ps-stat { font-size: 22px; font-weight: 600; line-height: 1.1; }
		</style>`).appendTo(document.head);
	}

	refresh() {
		frappe.call("polystore.api.health.status").then((r) => this.render_status(r.message || {}));
		frappe.call("polystore.api.catalog.stats").then((r) => this.render_stats(r.message || {}));
		if (this.book) this.load_record(this.book);
		if (this.member_name) this.load_member(this.member_name);
	}

	render_status(health) {
		this.health = health;
		this.render_status_cards();
	}

	render_stats(stats) {
		this.stats = stats;
		this.render_status_cards();
	}

	render_status_cards() {
		const health = this.health || {};
		const stats = this.stats || {};
		if (!this.health || !this.stats) return;

		const cards = [
			{
				title: "MariaDB",
				subtitle: "identity, links, indexed fields",
				value: `${stats.sql ? stats.sql.books : 0} books · ${stats.sql ? stats.sql.members : 0} members · ${stats.sql ? stats.sql.loans : 0} loans`,
				ok: true,
				detail: "relational",
			},
			{
				title: "MongoDB",
				subtitle: "free-form attribute documents",
				value: `${stats.mongo ? stats.mongo.documents : 0} documents`,
				ok: health.document_store && health.document_store.ok,
				detail: health.document_store && health.document_store.ok
					? `v${health.document_store.version}`
					: (health.document_store || {}).error,
			},
			{
				title: "Neo4j",
				subtitle: "BORROWED and FOLLOWS edges",
				value: `${stats.graph ? stats.graph.nodes : 0} nodes · ${stats.graph ? stats.graph.edges : 0} edges`,
				ok: health.graph_store && health.graph_store.ok,
				detail: health.graph_store && health.graph_store.ok
					? `v${health.graph_store.version}`
					: (health.graph_store || {}).error,
			},
		];

		this.$body.find(".ps-status").html(
			cards
				.map(
					(card) => `
			<div class="col-md-4">
				<div class="ps-panel">
					<div class="ps-engine">
						<span>${card.title}</span>
						<span class="indicator-pill ${card.ok ? "green" : "red"}">${card.ok ? "connected" : "unavailable"}</span>
					</div>
					<div class="ps-stat">${frappe.utils.escape_html(String(card.value))}</div>
					<div class="ps-hint" style="margin:4px 0 0">${card.subtitle} · ${frappe.utils.escape_html(String(card.detail || ""))}</div>
				</div>
			</div>`
				)
				.join("")
		);
	}

	build_record_panel() {
		const $panel = $(`
			<div class="ps-panel">
				<h5>One record, three stores</h5>
				<p class="ps-hint">Pick a book to see the same record as each engine holds it. Nothing here is duplicated — each store owns a different part.</p>
				<div class="ps-picker" style="max-width:320px"></div>
				<div class="row ps-three" style="margin-top:10px"></div>
			</div>
		`).appendTo(this.$body.find(".ps-record"));

		this.picker = frappe.ui.form.make_control({
			parent: $panel.find(".ps-picker"),
			df: {
				fieldtype: "Link",
				options: "Library Book",
				label: "Book",
				placeholder: "Select a book",
				onchange: () => {
					const value = this.picker.get_value();
					if (value) this.load_record(value);
				},
			},
			render_input: true,
		});

		frappe.db.get_list("Library Book", { limit: 1, order_by: "title" }).then((rows) => {
			if (rows && rows.length) this.picker.set_value(rows[0].name);
		});
	}

	load_record(book) {
		this.book = book;
		frappe
			.call("polystore.api.catalog.record_across_stores", { book })
			.then((r) => this.render_record(r.message || {}));
	}

	render_record(data) {
		const sql = data.sql || {};
		const graph = data.graph || {};
		const sql_rows = ["title", "author", "isbn", "media_type", "status", "follows"]
			.map((key) => `<div class="ps-kv"><span>${key}</span>${frappe.utils.escape_html(String(sql[key] || "—"))}</div>`)
			.join("");

		const borrowers = (graph.borrowers || [])
			.map((row) => frappe.utils.escape_html(row.member))
			.join(", ");
		const chain = (graph.chain || []).map((hop) => frappe.utils.escape_html(hop.title)).join(" → ");

		this.$body.find(".ps-three").html(`
			<div class="col-md-4">
				<div class="ps-engine">MariaDB <span class="text-muted">tabLibrary Book</span></div>
				${sql_rows}
			</div>
			<div class="col-md-4">
				<div class="ps-engine">MongoDB <span class="text-muted">${data.collection}.library_book</span></div>
				${
					Object.keys(data.mongo || {}).length
						? `<pre class="ps-json">${frappe.utils.escape_html(JSON.stringify(data.mongo, null, 2))}</pre>`
						: `<p class="ps-empty">No attribute document.</p>`
				}
			</div>
			<div class="col-md-4">
				<div class="ps-engine">Neo4j <span class="text-muted">graph</span></div>
				${
					data.graph_error
						? `<p class="ps-empty">${frappe.utils.escape_html(data.graph_error)}</p>`
						: `<div class="ps-kv"><span>borrowed by</span>${borrowers || "—"}</div>
						   <div class="ps-kv"><span>follows</span>${(graph.follows || []).join(", ") || "—"}</div>
						   <div class="ps-kv"><span>followed by</span>${(graph.followed_by || []).join(", ") || "—"}</div>
						   <div class="ps-kv"><span>series chain</span>${chain || "—"}</div>`
				}
			</div>
		`);
	}

	build_member_panel() {
		const $panel = $(`
			<div class="ps-panel">
				<h5>A member, split three ways</h5>
				<p class="ps-hint">Contact and membership details are SQL columns. The reader profile is a MongoDB document. Who they know is a set of Neo4j edges with no SQL row behind it.</p>
				<div class="ps-member-picker" style="max-width:320px"></div>
				<div class="row ps-member-three" style="margin-top:10px"></div>
			</div>
		`).appendTo(this.$body.find(".ps-member-record"));

		this.member_picker = frappe.ui.form.make_control({
			parent: $panel.find(".ps-member-picker"),
			df: {
				fieldtype: "Link",
				options: "Library Member",
				label: "Member",
				onchange: () => {
					const value = this.member_picker.get_value();
					if (value) this.load_member(value);
				},
			},
			render_input: true,
		});

		frappe.db.get_list("Library Member", { limit: 1, order_by: "member_name" }).then((rows) => {
			if (rows && rows.length) this.member_picker.set_value(rows[0].name);
		});
	}

	load_member(member) {
		this.member_name = member;
		frappe
			.call("polystore.api.catalog.member_across_stores", { member })
			.then((r) => this.render_member(r.message || {}));
	}

	render_member(data) {
		const sql = data.sql || {};
		const graph = data.graph || {};
		const rows = ["member_name", "email", "phone", "membership_type", "joined_on", "status"]
			.map((key) => `<div class="ps-kv"><span>${key}</span>${frappe.utils.escape_html(String(sql[key] || "—"))}</div>`)
			.join("");

		const knows = (graph.knows || []).map((row) => frappe.utils.escape_html(row.member_name)).join(", ");
		const suggested = (graph.suggestions || [])
			.map((row) => `${frappe.utils.escape_html(row.member_name)} (${row.mutuals})`)
			.join(", ");

		this.$body.find(".ps-member-three").html(`
			<div class="col-md-4">
				<div class="ps-engine">MariaDB <span class="text-muted">tabLibrary Member</span></div>
				${rows}
			</div>
			<div class="col-md-4">
				<div class="ps-engine">MongoDB <span class="text-muted">polystore.library_member</span></div>
				${
					Object.keys(data.mongo || {}).length
						? `<pre class="ps-json">${frappe.utils.escape_html(JSON.stringify(data.mongo, null, 2))}</pre>`
						: `<p class="ps-empty">No profile document.</p>`
				}
			</div>
			<div class="col-md-4">
				<div class="ps-engine">Neo4j <span class="text-muted">graph</span></div>
				${
					data.graph_error
						? `<p class="ps-empty">${frappe.utils.escape_html(data.graph_error)}</p>`
						: `<div class="ps-kv"><span>knows</span>${knows || "—"}</div>
						   <div class="ps-kv"><span>2 hops out</span>${suggested || "—"}</div>
						   <div class="ps-kv"><span>borrowed</span>${frappe.utils.escape_html((graph.borrowed || []).join(", ")) || "—"}</div>`
				}
			</div>
		`);
	}

	build_search_panel() {
		const $panel = $(`
			<div class="ps-panel">
				<h5>Search a field SQL has never heard of</h5>
				<p class="ps-hint">These keys exist only inside MongoDB documents — there is no column for them. Try <code>narrator</code> = <code>Rob Inglis</code>, or <code>series</code> = <code>Dune</code>.</p>
				<div class="row">
					<div class="col-md-5 ps-key"></div>
					<div class="col-md-5 ps-value"></div>
					<div class="col-md-2" style="padding-top:24px"><button class="btn btn-sm btn-primary ps-run">Search</button></div>
				</div>
				<div class="ps-results" style="margin-top:10px"></div>
			</div>
		`).appendTo(this.$body.find(".ps-search"));

		this.key = this.make_data_control($panel.find(".ps-key"), "Attribute key", "series");
		this.value = this.make_data_control($panel.find(".ps-value"), "Value", "Dune");

		$panel.find(".ps-run").on("click", () => {
			frappe
				.call("polystore.api.catalog.search_by_attribute", {
					key: this.key.get_value(),
					value: this.value.get_value(),
				})
				.then((r) => {
					const rows = r.message || [];
					$panel.find(".ps-results").html(
						rows.length
							? `<ul class="ps-list">${rows
									.map(
										(row) =>
											`<li><a href="/app/library-book/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.title)}</a> <span class="text-muted">— ${frappe.utils.escape_html(row.author || "")}</span></li>`
									)
									.join("")}</ul>`
							: `<p class="ps-empty">No document matched.</p>`
					);
				});
		});
	}

	build_graph_panel() {
		const $panel = $(`
			<div class="ps-panel">
				<h5>Traversal</h5>
				<p class="ps-hint">Two hops through the borrowing graph: readers who took out what this member took out, and what else they read.</p>
				<div class="ps-member" style="max-width:320px"></div>
				<div class="ps-recs" style="margin-top:10px"></div>
			</div>
		`).appendTo(this.$body.find(".ps-graph"));

		this.member = frappe.ui.form.make_control({
			parent: $panel.find(".ps-member"),
			df: {
				fieldtype: "Link",
				options: "Library Member",
				label: "Member",
				onchange: () => {
					const value = this.member.get_value();
					if (!value) return;

					frappe
						.call("polystore.api.catalog.recommendations", { member: value })
						.then((r) => {
							const rows = r.message || [];
							$panel.find(".ps-recs").html(
								rows.length
									? `<ul class="ps-list">${rows
											.map(
												(row) =>
													`<li><a href="/app/library-book/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.title)}</a> <span class="text-muted">— ${row.shared_readers} shared reader(s)</span></li>`
											)
											.join("")}</ul>`
									: `<p class="ps-empty">No suggestions — this member shares no books with anyone yet.</p>`
							);
						});
				},
			},
			render_input: true,
		});

		frappe.db.get_list("Library Member", { limit: 1, order_by: "member_name" }).then((rows) => {
			if (rows && rows.length) this.member.set_value(rows[0].name);
		});
	}

	make_data_control($parent, label, placeholder) {
		return frappe.ui.form.make_control({
			parent: $parent,
			df: { fieldtype: "Data", label, placeholder },
			render_input: true,
		});
	}
}
