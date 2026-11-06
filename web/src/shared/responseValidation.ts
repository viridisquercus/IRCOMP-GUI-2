/** Schema keywords emitted by the Python models for API responses. */
export type Schema = {
  $ref?: string;
  type?: string;
  const?: unknown;
  enum?: unknown[];
  anyOf?: Schema[];
  oneOf?: Schema[];
  properties?: Record<string, Schema>;
  required?: string[];
  additionalProperties?: boolean | Schema;
  propertyNames?: Schema;
  patternProperties?: Record<string, Schema>;
  items?: Schema;
  minItems?: number;
  maxItems?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  [keyword: string]: unknown;
};

/** Check response data before it enters the shared state. */
export function matchesSchema(
  value: unknown,
  schema: Schema,
  definitions: Record<string, Schema>,
  depth = 0,
): boolean {
  if (depth > 256) return false;
  const matches = (item: unknown, rule: Schema) =>
    matchesSchema(item, rule, definitions, depth + 1);
  if (schema.$ref) {
    const rule = definitions[schema.$ref.split("/").at(-1)!];
    return !!rule && matches(value, rule);
  }
  if ("const" in schema && value !== schema.const) return false;
  if (schema.enum && !schema.enum.includes(value)) return false;
  if (schema.anyOf && !schema.anyOf.some((rule) => matches(value, rule)))
    return false;
  if (
    schema.oneOf &&
    schema.oneOf.filter((rule) => matches(value, rule)).length !== 1
  )
    return false;
  switch (schema.type) {
    case "null":
      return value === null;
    case "boolean":
      return typeof value === "boolean";
    case "integer":
    case "number":
      return (
        typeof value === "number" &&
        Number.isFinite(value) &&
        (schema.type !== "integer" || Number.isSafeInteger(value)) &&
        (schema.minimum === undefined || value >= schema.minimum) &&
        (schema.maximum === undefined || value <= schema.maximum) &&
        (schema.exclusiveMinimum === undefined ||
          value > schema.exclusiveMinimum) &&
        (schema.exclusiveMaximum === undefined ||
          value < schema.exclusiveMaximum)
      );
    case "string":
      return (
        typeof value === "string" &&
        (schema.minLength === undefined ||
          [...value].length >= schema.minLength) &&
        (schema.maxLength === undefined ||
          [...value].length <= schema.maxLength) &&
        (!schema.pattern || new RegExp(schema.pattern).test(value))
      );
    case "array":
      return (
        Array.isArray(value) &&
        (schema.minItems === undefined || value.length >= schema.minItems) &&
        (schema.maxItems === undefined || value.length <= schema.maxItems) &&
        value.every((item) => !schema.items || matches(item, schema.items))
      );
    case "object": {
      if (!value || typeof value !== "object" || Array.isArray(value))
        return false;
      const object: Record<string, unknown> = value as Record<string, unknown>;
      const properties = schema.properties ?? {};
      if (schema.required?.some((key) => !Object.hasOwn(object, key)))
        return false;
      return Object.entries(object).every(([key, item]) => {
        if (schema.propertyNames && !matches(key, schema.propertyNames))
          return false;
        if (Object.hasOwn(properties, key))
          return matches(item, properties[key]);
        const patterns = Object.entries(schema.patternProperties ?? {}).filter(
          ([pattern]) => new RegExp(pattern).test(key),
        );
        if (patterns.length)
          return patterns.every(([, rule]) => matches(item, rule));
        const extra = schema.additionalProperties;
        return (
          extra !== false && (typeof extra !== "object" || matches(item, extra))
        );
      });
    }
    default:
      return true;
  }
}
