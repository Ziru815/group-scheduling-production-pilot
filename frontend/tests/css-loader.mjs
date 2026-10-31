export async function load(url, context, nextLoad) {
  if (url.endsWith('.css')) {
    return {
      format: 'module',
      shortCircuit: true,
      source: 'export default {}',
    }
  }
  if (url.endsWith('/src/api/client.ts')) {
    return {
      format: 'module',
      shortCircuit: true,
      source: `
        const unavailable = () => Promise.reject(new Error('Unexpected API call in component test'))
        export const api = { get: unavailable, post: unavailable, patch: unavailable, put: unavailable }
        export const isApiError = () => false
      `,
    }
  }
  return nextLoad(url, context)
}
