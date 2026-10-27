// Turns the demo build (dist-demo/) into ONE self-contained HTML file with the
// CSS and JS inlined, for hosts that only serve a single page (e.g. a Claude
// Artifact). Output: dist-demo/group-scheduler-demo.html
//
// The host wraps the file in its own <html>/<head>/<body>, so the output is
// just a <title>, the styles, the root element and the script.
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const dir = 'dist-demo'
const html = readFileSync(join(dir, 'index.html'), 'utf8')

const cssHrefs = [...html.matchAll(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"/g)].map((m) => m[1])
const jsSrcs = [...html.matchAll(/<script[^>]+type="module"[^>]+src="([^"]+)"/g)].map((m) => m[1])
if (jsSrcs.length !== 1) throw new Error(`Expected one module script, found ${jsSrcs.length}. Is code splitting off?`)

const read = (ref) => readFileSync(join(dir, ref.replace(/^\.\//, '')), 'utf8')
const css = cssHrefs.map(read).join('\n')
// A literal "</script" inside the bundle would end the inline <script> early.
const js = read(jsSrcs[0]).replace(/<\/script/gi, '<\\/script')

const out = `<title>Group Scheduler</title>
<style>
${css}
</style>
<div id="root"></div>
<script type="module">
${js}
</script>
`
const file = join(dir, 'group-scheduler-demo.html')
writeFileSync(file, out)
console.log(`Wrote ${file} (${(out.length / 1024).toFixed(0)} KB)`)
