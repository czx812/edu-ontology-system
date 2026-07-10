<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>数据源检索</h1>
        <p>检索 PDF 解析出的教育标准编码、中文名称及其来源。</p>
      </div>
      <button :disabled="loading" @click="search">{{ loading ? "检索中..." : "检索" }}</button>
    </div>

    <div class="search-panel">
      <input v-model="keyword" placeholder="输入标准编码或中文名称，例如 JCTB0203、工作简历" @keyup.enter="search" />
      <select v-model="scope">
        <option value="all">全部范围</option>
        <option value="class">数据子类</option>
        <option value="property">数据属性</option>
      </select>
    </div>

    <p v-if="notice" class="notice">{{ notice }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="stats-row">
      <div class="stat"><strong>{{ results.length }}</strong><span>匹配结果</span></div>
      <div class="stat"><strong>{{ sourceSummary.classes }}</strong><span>数据子类</span></div>
      <div class="stat"><strong>{{ sourceSummary.properties }}</strong><span>数据属性</span></div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr><th>编码</th><th>中文名称</th><th>类型</th><th>所属类</th><th>来源</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in visibleResults" :key="item.key" :class="{ child: item.isChild }">
            <td class="code">{{ item.code || "-" }}</td>
            <td class="name">
              <button v-if="item.type_key === 'class' && item.childCount" class="expand" @click="toggle(item.code)" :aria-label="`${expandedCodes.has(item.code) ? '收起' : '展开'} ${item.name}`">
                {{ expandedCodes.has(item.code) ? "▾" : "▸" }}
              </button>
              {{ item.name || "-" }}
            </td>
            <td><span class="tag">{{ item.type }}</span></td>
            <td>{{ item.parent_name || item.domain || "-" }}</td>
            <td class="path">{{ sourceLabel(item) }}</td>
          </tr>
          <tr v-if="!visibleResults.length"><td colspan="5">暂无匹配结果</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { searchDataSources } from "../api/request";

const keyword = ref("");
const scope = ref("all");
const results = ref([]);
const loading = ref(false);
const error = ref("");
const notice = ref("");
const sourceMetadata = ref({ classes: [], properties: [] });
const expandedCodes = ref(new Set());

const sourceSummary = computed(() => ({
  classes: sourceMetadata.value.classes?.length || 0,
  properties: sourceMetadata.value.properties?.length || 0,
}));

const visibleResults = computed(() => {
  const all = results.value;
  const childrenByParent = new Map();
  for (const item of all) {
    if (item.type_key === "property" && item.parent) {
      const list = childrenByParent.get(item.parent) || [];
      list.push(item);
      childrenByParent.set(item.parent, list);
    }
  }
  const rows = [];
  for (const item of all) {
    if (item.type_key !== "class") continue;
    const children = childrenByParent.get(item.code) || [];
    rows.push({ ...item, childCount: children.length });
    if (expandedCodes.value.has(item.code)) rows.push(...children.map((child) => ({ ...child, isChild: true })));
  }
  // A direct property search may not include its parent row; still show it.
  rows.push(...all.filter((item) => item.type_key !== "class" && (!item.parent || !all.some((parent) => parent.type_key === "class" && parent.code === item.parent))));
  return rows;
});

function toggle(code) {
  const next = new Set(expandedCodes.value);
  next.has(code) ? next.delete(code) : next.add(code);
  expandedCodes.value = next;
}

function sourceLabel(item) {
  const source = item.source && typeof item.source === "object" ? item.source : {};
  const file = source.file || item.source_file || item.filename || "-";
  const page = source.page ?? item.page;
  return page !== undefined && page !== null && page !== "" ? `${file} 第${page}页` : file;
}

async function search() {
  loading.value = true;
  error.value = "";
  notice.value = "";
  try {
    const res = await searchDataSources({ keyword: keyword.value, scope: scope.value });
    if (res.data.data_type !== "source") throw new Error("数据源接口返回了非 source 数据");
    results.value = [
      ...(res.data.classes || []).map((item) => ({ ...item, type_key: "class", key: `class-${item.code}` })),
      ...(res.data.properties || []).map((item) => ({ ...item, type_key: "property", key: `property-${item.code}` })),
    ];
    sourceMetadata.value = {
      classes: res.data.classes || [],
      properties: res.data.properties || [],
    };
    // Source records are the primary result; show their standard properties
    // immediately instead of hiding them behind an ontology-style tree.
    expandedCodes.value = new Set((res.data.classes || []).map((item) => item.code).filter(Boolean));
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || "检索失败";
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
.code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: nowrap; }
.child .name, .child .code { padding-left: 28px; }
.expand { border: 0; background: transparent; color: #2563eb; padding: 0 6px 0 0; font-size: 16px; }
.path { max-width: 260px; word-break: break-all; }
.tag { display: inline-block; padding: 3px 8px; border-radius: 999px; background: #e0f2fe; color: #075985; font-size: 12px; }
.notice { color: #0369a1; }
.error { color: #b91c1c; }
@media (max-width: 720px) { .toolbar, .search-panel { grid-template-columns: 1fr; display: grid; } .stats-row { grid-template-columns: repeat(2, 1fr); } }
</style>

