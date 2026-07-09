(function(){
  const filter=document.getElementById('filter');
  if(filter){
    filter.addEventListener('input',()=>{
      const needle=filter.value.toLowerCase();
      document.querySelectorAll('#flows tbody tr').forEach(row=>{
        row.style.display=row.innerText.toLowerCase().includes(needle)?'':'none';
      });
    });
  }
  document.querySelectorAll('.data-table tbody tr').forEach(row=>{
    row.addEventListener('mouseenter',()=>row.classList.add('row-active'));
    row.addEventListener('mouseleave',()=>row.classList.remove('row-active'));
  });
})();
