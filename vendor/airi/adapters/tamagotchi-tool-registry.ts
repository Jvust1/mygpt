/**
 * Adapted from Project AIRI's MIT-licensed plugin-sdk-tamagotchi tool registry.
 * Upstream: https://github.com/SEKAI-OS/AIRI (canonical: https://github.com/moeru-ai/airi)
 * Source module: packages/plugin-sdk-tamagotchi/src/tools/registry.ts
 */

export interface CompanionToolDefinition {
  id: string
  title: string
  description: string
  activation?: { keywords?: string[]; patterns?: RegExp[] }
  parameters: Record<string, unknown>
}

export interface CompanionToolRecord {
  ownerSessionId: string
  ownerExtensionId: string
  ownerModuleId?: string
  tool: CompanionToolDefinition
  availability?: () => boolean | Promise<boolean>
  execute: (input: unknown) => unknown | Promise<unknown>
}

export class CompanionToolRegistry {
  private readonly tools = new Map<string, CompanionToolRecord>()

  private key(ownerExtensionId: string, toolId: string) {
    return `${ownerExtensionId}:${toolId}`
  }

  register(record: CompanionToolRecord) {
    this.tools.set(this.key(record.ownerExtensionId, record.tool.id), record)
    return record
  }

  unregister(ownerExtensionId: string, toolId: string) {
    return this.tools.delete(this.key(ownerExtensionId, toolId))
  }

  unregisterOwnerSession(ownerSessionId: string) {
    for (const [key, record] of this.tools) {
      if (record.ownerSessionId === ownerSessionId)
        this.tools.delete(key)
    }
  }

  unregisterOwnerScope(ownerSessionId: string, ownerModuleId?: string) {
    for (const [key, record] of this.tools) {
      if (record.ownerSessionId === ownerSessionId && record.ownerModuleId === ownerModuleId)
        this.tools.delete(key)
    }
  }

  async listAvailableDescriptors() {
    const result = []
    for (const record of this.tools.values()) {
      if (await record.availability?.() === false)
        continue
      result.push({
        id: record.tool.id,
        title: record.tool.title,
        description: record.tool.description,
        activation: {
          keywords: [...(record.tool.activation?.keywords ?? [])],
          patterns: (record.tool.activation?.patterns ?? []).map(pattern => pattern.source),
        },
      })
    }
    return result
  }

  async invoke(ownerExtensionId: string, toolId: string, input: unknown) {
    const key = this.key(ownerExtensionId, toolId)
    const record = this.tools.get(key)
    if (!record)
      throw new Error(`Companion extension tool not found: ${key}`)
    if (await record.availability?.() === false)
      throw new Error(`Companion extension tool unavailable: ${key}`)
    return await record.execute(input)
  }
}
