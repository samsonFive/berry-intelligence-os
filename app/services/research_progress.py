"""One explicit research request, streamed without another provider execution."""
import asyncio
import json


async def events(operation):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=1)
    closed = False

    def latest(value):
        if closed:
            return
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(value)

    def progress(value):
        # This callback can be invoked from the bounded source-capture worker.
        if not closed:
            try:
                loop.call_soon_threadsafe(latest, {'type':'progress', **value})
            except RuntimeError:
                pass  # The disconnected request's event loop has already closed.

    async def run():
        try:
            response = await operation(progress)
            return {'type':'complete', 'html':response.body.decode('utf-8')}
        except Exception:
            # Provider exceptions may contain credentials. Keep those off the wire.
            return {'type':'error', 'message':'The source check could not finish. Saved intelligence remains available.'}

    task = asyncio.create_task(run())
    pending = None
    try:
        yield json.dumps({'type':'progress','stage':'starting','items':[]})+'\n'
        while not task.done():
            pending = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({pending,task},return_when=asyncio.FIRST_COMPLETED)
            if pending in done:
                yield json.dumps(pending.result(),ensure_ascii=True)+'\n'
            else:
                pending.cancel()
                await asyncio.gather(pending,return_exceptions=True)
        yield json.dumps(await task,ensure_ascii=True)+'\n'
    finally:
        closed = True
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.gather(pending,return_exceptions=True)
        if not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
