"""Stop/reap only a Popen-owned direct child; no PID/group enumeration."""
import signal,subprocess,traceback
def stop_and_reap(process,grace_s,pidfd=None):
 actions=[];errors=[]
 def send(sig):
  if process.poll() is not None:return
  if pidfd is not None:signal.pidfd_send_signal(pidfd,sig)
  else:process.send_signal(sig) # Unreaped direct child Popen prevents PID reuse.
  actions.extend(['pidfd' if pidfd is not None else 'direct_Popen_handle',signal.Signals(sig).name])
 try:
  if process.poll() is None:
   try:send(signal.SIGTERM)
   except ProcessLookupError:pass
   process.wait(timeout=grace_s)
 except subprocess.TimeoutExpired:pass
 except BaseException:errors.append(traceback.format_exc())
 finally:
  try:
   if process.poll() is None:
    try:send(signal.SIGKILL)
    except ProcessLookupError:pass
  except BaseException:errors.append(traceback.format_exc())
  try:returncode=process.wait()
  except BaseException:
   errors.append(traceback.format_exc());returncode=process.returncode
 return {'return_code':returncode,'actual_child_waited':returncode is not None,'actions':actions,'cleanup_errors':errors}
