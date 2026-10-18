import {PGlite} from '@electric-sql/pglite';
import {createInterface} from 'node:readline';

const db = new PGlite();
await db.waitReady;
process.stdout.write(JSON.stringify({ready:true})+'\n');
for await (const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
  try {
    const request=JSON.parse(line);
    if(request.close){await db.close();process.exit(0);}
    const result=request.exec ? await db.exec(request.sql) : await db.query(request.sql,request.params??[]);
    process.stdout.write(JSON.stringify({result})+'\n');
  } catch(error) {
    process.stdout.write(JSON.stringify({error:error.message,code:error.code})+'\n');
  }
}
