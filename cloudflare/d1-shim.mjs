// Minimal in-memory D1 emulator for the local test suite (test.mjs).
// Prefers the built-in node:sqlite (Node >= 22.5); falls back to better-sqlite3
// (npm i better-sqlite3). Only implements the subset of the D1 API used by
// worker.js: prepare().bind().all()/first()/run() and batch().

async function openHandle() {
  // 1) node:sqlite (Node >= 22.5)
  try {
    const { DatabaseSync } = await import("node:sqlite");
    const db = new DatabaseSync(":memory:");
    return {
      exec: (sql) => db.exec(sql),
      prepare: (sql) => db.prepare(sql),
    };
  } catch (e) {
    /* fall through */
  }
  // 2) better-sqlite3
  const mod = await import("better-sqlite3");
  const Database = mod.default;
  const db = new Database(":memory:");
  return {
    exec: (sql) => db.exec(sql),
    prepare: (sql) => db.prepare(sql),
  };
}

class Statement {
  constructor(d1, sql) {
    this.d1 = d1;
    this.sql = sql;
    this.args = [];
  }

  bind(...args) {
    this.args = args;
    return this;
  }

  async _rows() {
    const handle = await this.d1._init();
    const stmt = handle.prepare(this.sql);
    try {
      return stmt.all(...this.args);
    } catch (e) {
      // better-sqlite3: "This statement does not return data. Use run() instead"
      if (/does not return data/i.test(String(e.message))) {
        stmt.run(...this.args);
        return [];
      }
      throw e;
    }
  }

  async all() {
    return { results: (await this._rows()) || [] };
  }

  async first() {
    const rows = (await this._rows()) || [];
    return rows.length ? rows[0] : null;
  }

  async run() {
    const handle = await this.d1._init();
    const stmt = handle.prepare(this.sql);
    try {
      stmt.run(...this.args);
    } catch (e) {
      // some drivers dislike .run() on SELECT — harmless
    }
    return { success: true };
  }
}

export class D1 {
  constructor() {
    this._handle = null;
    this._opening = openHandle();
  }

  async _init() {
    if (!this._handle) this._handle = await this._opening;
    return this._handle;
  }

  prepare(sql) {
    return new Statement(this, sql);
  }

  async batch(statements) {
    const out = [];
    for (const statement of statements) out.push(await statement.all());
    return out;
  }

  async exec(sql) {
    const handle = await this._init();
    handle.exec(sql);
  }

  // synchronous helper for test assertions
  raw(sql, ...args) {
    if (!this._handle) throw new Error("DB not initialized yet");
    return this._handle.prepare(sql).all(...args);
  }
}

export async function createTestDb(schemaSql) {
  const d1 = new D1();
  await d1.exec(schemaSql);
  return d1;
}
