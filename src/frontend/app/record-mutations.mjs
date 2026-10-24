/** Keep an acknowledged record mutation separate from failures while refreshing its views. */
export async function refreshAfterRecordChange(refresh,onRefreshError){
  try{await refresh();return true;}
  catch(error){
    const detail=error instanceof Error?error.message:'The workspace could not be refreshed.';
    onRefreshError(`The record change was saved, but the workspace could not refresh. Reload the workspace before making another change. ${detail}`);
    return false;
  }
}
