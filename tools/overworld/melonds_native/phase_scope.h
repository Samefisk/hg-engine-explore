#ifndef OW_MELONDS_PHASE_SCOPE_H
#define OW_MELONDS_PHASE_SCOPE_H
#include <stdint.h>
// Private native instrumentation, not a guest or public callback interface.
uint32_t MD_PhaseEnter(void* handle, uint32_t phase) noexcept;
void MD_PhaseLeave(void* handle, uint32_t token) noexcept;
struct MD_PhaseScope {
    void* handle;
    uint32_t token;
    MD_PhaseScope(void* h, uint32_t phase) noexcept : handle(h), token(MD_PhaseEnter(h, phase)) {}
    ~MD_PhaseScope() noexcept { if(token) MD_PhaseLeave(handle, token); }
    MD_PhaseScope(const MD_PhaseScope&)=delete;
    MD_PhaseScope& operator=(const MD_PhaseScope&)=delete;
};
#endif
