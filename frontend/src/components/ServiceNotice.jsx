// A distinct "try again later" banner for when the backend reports the AI service is
// unavailable (quota exhausted or high demand — see isServiceUnavailable in api.js). Kept
// visually separate from a plain validation/bug error so it reads as "this isn't broken,
// just busy" rather than blending into every other red error message.
export function ServiceNotice({ message }) {
  return (
    <p className="service-notice">
      <span aria-hidden="true">⚠️</span>
      <span>{message}</span>
    </p>
  );
}
