# landing/atual.html

Copia **byte a byte** da pagina inicial que rodava em producao antes da publicacao do app
multi-tenant (o app antigo, "Academia System - Transforme sua vida"). Guardada aqui por
decisao do dono: a landing atual **nao** deve ser substituida pela pagina da vitrine do app
novo sem decisao explicita.

Quem serve: `nginx/default.conf`, no bloco `location = /` -- arquivo estatico, sem passar
pelo Django. O unico asset externo e `/static/images/landing/hero-gym.webp`, que existe no
`static/` do projeto e continua sendo servido por `/static/`.

Para passar a usar a pagina da vitrine do app novo na raiz: remova o bloco `location = /` do
`nginx/default.conf` e reconstrua a imagem do nginx.
