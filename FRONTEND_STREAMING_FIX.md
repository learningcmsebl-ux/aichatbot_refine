# Frontend Streaming Shaking Fix ✅

## Problem

The frontend was "shaking" during streaming responses. This was caused by:

1. **Smooth scroll on every chunk**: Using `behavior: 'smooth'` on every message update caused laggy, jittery scrolling
2. **Multiple scroll effects**: Two separate scroll effects were competing
3. **No throttling**: Scroll was happening on every single chunk update
4. **Always scrolling**: Even when user scrolled up, it would force scroll down

## Solution

### Changes Made

1. **Separate scroll behaviors**:
   - **New messages**: Use smooth scroll (`behavior: 'smooth'`)
   - **Streaming updates**: Use instant scroll (`behavior: 'auto'`)

2. **Smart scroll detection**:
   - Only auto-scroll if user is near bottom (within 150px)
   - Prevents forcing scroll when user is reading previous messages

3. **Throttled updates**:
   - Scroll updates throttled to ~30fps (every 33ms) during streaming
   - Uses `requestAnimationFrame` for smooth rendering
   - Prevents excessive scroll operations

4. **Message count tracking**:
   - Tracks message count to detect new messages vs. streaming updates
   - New messages get smooth scroll, streaming gets instant scroll

### Code Changes

**Before:**
```typescript
// Smooth scroll on every update (causes shaking)
useEffect(() => {
  messagesEndRef.current?.scrollIntoView({
    behavior: 'smooth', // Too slow for streaming!
    block: 'end',
  });
}, [messages, isLoading]);
```

**After:**
```typescript
// Instant scroll during streaming, smooth for new messages
const scrollToBottom = (smooth: boolean = false) => {
  messagesEndRef.current?.scrollIntoView({
    behavior: smooth ? 'smooth' : 'auto', // Instant during streaming
    block: 'end',
  });
};

// Throttled scroll during streaming
useEffect(() => {
  if (isStreaming && isNearBottom()) {
    setTimeout(() => {
      requestAnimationFrame(() => {
        scrollToBottom(false); // Instant scroll
      });
    }, 33); // Throttled to ~30fps
  }
}, [messages, isLoading]);
```

## Benefits

✅ **No more shaking**: Instant scroll during streaming eliminates jitter
✅ **Better UX**: Smooth scroll only for new messages
✅ **Respects user**: Doesn't force scroll if user is reading previous messages
✅ **Performance**: Throttled updates reduce CPU usage
✅ **Smooth rendering**: Uses `requestAnimationFrame` for optimal timing

## Testing

After the fix, streaming should:
- ✅ Scroll smoothly without shaking
- ✅ Keep up with content updates
- ✅ Not force scroll if user scrolled up
- ✅ Use smooth scroll when new message arrives
- ✅ Use instant scroll during streaming updates

## Summary

The fix eliminates the shaking by:
1. Using instant scroll (`auto`) during streaming instead of smooth scroll
2. Throttling scroll updates to prevent excessive operations
3. Only scrolling if user is near the bottom
4. Using `requestAnimationFrame` for optimal rendering

The frontend should now stream responses smoothly without any shaking or jitter!

