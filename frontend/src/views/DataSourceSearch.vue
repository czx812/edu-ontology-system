<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>数据源检索</h1>
        <p>检索已生成本体中的类、属性、关系与来源文件，辅助追溯数据项依据。</p>
      </div>
      <button :disabled="loading" @click="search">{{ loading ? "检索中..." : "检索" }}</button>
    </div>

    <div class="search-panel">
      <input v-model="keyword" placeholder="输入类名、数据项编号、字段名、文件名或描述" @keyup.enter="search" />
      <select v-model="scope">
        <option value="all">全部范围</option>
        <option value="class">类</option>
        <option value="property">属性</option>
        <option value="relation">关系</option>
        <option value="file">来源文件</option>
      </select>
    </div>

    <p v-if="notice" class="notice">{{ notice }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="stats-row">
      <div class="stat"><strong>{{ results.length }}</strong><span>匹配结果</span></div>
      <div class="stat"><strong>{{ sourceSummary.classes }}</strong><span>类</span></div>
      <div class="stat"><strong>{{ sourceSummary.properties }}</strong><span>属性</span></div>
      <div class="stat"><strong>{{ sourceSummary.relations }}</strong><span>关系</span></div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr><th>类型</th><th>名称/编号</th><th>领域</th><th>来源文件</th><th>页/表/行</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in results" :key="item.key">
            <td><span class="tag">{{ item.type }}</span></td>
            <td class="name">{{ item.name }}</td>
            <td>{{ item.domain || "-" }}</td>
            <td class="path">{{ item.source || "-" }}</td>
            <td>{{ item.description || "-" }}</td>
          </tr>
          <tr v-if="!results.length"><td colspan="6">暂无匹配结果</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { getMyGenerations, searchDataSources } from "../api/request";

const keyword = ref("");
const scope = ref("all");
const results = ref([]);
const loading = ref(false);
const error = ref("");
const notice = ref("");
const localIndex = ref([]);
const ontology = ref({ classes: [], properties: [], relations: [] });

const sourceSummary = computed(() => ({
  classes: ontology.value.classes?.length || 0,
  properties: ontology.value.properties?.length || 0,
  relations: ontology.value.relations?.length || 0,
}));

function readLocalOntology() {
  try {
    ontology.value = JSON.parse(localStorage.getItem("lastOntology") || "{}");
  } catch (err) {
    ontology.value = {};
  }
}

function itemText(item) {
  return [item.type, item.name, item.domain, item.source, item.description].join(" ").toLowerCase();
}

function buildLocalIndex(generations = []) {
  readLocalOntology();
  const list = [];
  for (const cls of ontology.value.classes || []) {
    list.push({ key: `class-${cls.name}`, type: "类", name: cls.name || cls.label, domain: cls.parent || "-", source: "当前本体", description: cls.description || cls.label || "" });
  }
  for (const prop of ontology.value.properties || []) {
    list.push({ key: `property-${prop.code || prop.name}`, type: "属性", name: `${prop.code || ""} ${prop.label || prop.name || ""}`.trim(), domain: prop.domain, source: prop.source_table || prop.source?.table_index || "当前本体", description: prop.description || prop.field_name || "" });
  }
  for (const rel of ontology.value.relations || []) {
    list.push({ key: `relation-${rel.source}-${rel.target}-${rel.type}`, type: "关系", name: `${rel.source} -> ${rel.target}`, domain: rel.type, source: "当前本体", description: rel.description || rel.reason || "" });
  }
  for (const item of generations) {
    list.push({ key: `file-${item.id}`, type: "来源文件", name: item.file_name, domain: item.status, source: item.structured_file || item.owl_file, description: `记录数 ${item.record_count || 0}，耗时 ${item.duration_ms || 0} ms` });
  }
  localIndex.value = list;
}

function filterLocalIndex() {
  const query = keyword.value.trim().toLowerCase();
  const selected = scope.value;
  const scopeMap = { class: "类", property: "属性", relation: "关系", file: "来源文件" };
  results.value = localIndex.value.filter((item) => {
    const scopeOk = selected === "all" || item.type === scopeMap[selected];
    const queryOk = !query || itemText(item).includes(query);
    return scopeOk && queryOk;
  });
}

async function search() {
  loading.value = true;
  error.value = "";
  notice.value = "";
  try {
    const res = await searchDataSources({ keyword: keyword.value, scope: scope.value });
    results.value = res.data.items || [];
  } catch (err) {
    try {
      const gen = await getMyGenerations();
      buildLocalIndex(gen.data.items || []);
      filterLocalIndex();
      notice.value = "当前使用本地本体与生成记录检索。";
    } catch (fallbackErr) {
      error.value = fallbackErr.response?.data?.detail || fallbackErr.message || "检索失败";
    }
  } finally {
    loading.value = false;
  }
}

onMounted(search);
</script>

<style scoped>
.page-shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.toolbar p { margin: 6px 0 0; color: #64748b; }
button { padding: 9px 14px; border: none; border-radius: 6px; background: #2563eb; color: white; cursor: pointer; }
button:disabled { opacity: .7; cursor: not-allowed; }
.search-panel { display: grid; grid-template-columns: 1fr 170px; gap: 10px; margin-bottom: 14px; }
input, select { min-width: 0; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; }
.stats-row { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin-bottom: 14px; }
.stat { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.stat strong { font-size: 22px; color: #0f172a; }
.stat span { color: #64748b; font-size: 13px; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }
th { background: #f8fafc; }
.name { font-weight: 700; color: #0f172a; }
.path { max-width: 260px; word-break: break-all; }
.tag { display: inline-block; padding: 3px 8px; border-radius: 999px; background: #e0f2fe; color: #075985; font-size: 12px; }
.notice { color: #0369a1; }
.error { color: #b91c1c; }
@media (max-width: 720px) { .toolbar, .search-panel { grid-template-columns: 1fr; display: grid; } .stats-row { grid-template-columns: repeat(2, 1fr); } }
</style>

